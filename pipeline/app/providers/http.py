"""HTTP client with quota accounting, retries and call logging. Stdlib only."""
from __future__ import annotations

import calendar
import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol


class ProviderError(RuntimeError):
    pass


class BudgetExceeded(ProviderError):
    pass


@dataclass
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: Any


class Transport(Protocol):
    def get(self, url: str, headers: dict[str, str]) -> HttpResponse: ...


class UrllibTransport:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def get(self, url: str, headers: dict[str, str]) -> HttpResponse:
        req = urllib.request.Request(url, headers={"Accept": "application/json, text/csv;q=0.9, */*;q=0.5", "User-Agent": "przewaga/0.4", **headers})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                headers = {k.lower(): v for k, v in r.headers.items()}
                return HttpResponse(r.status, headers, decode_body(r.read(), headers.get("content-type", "")))
        except urllib.error.HTTPError as e:
            body: Any
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:  # noqa: BLE001 - provider returned non-JSON error page
                body = None
            return HttpResponse(e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, body)


def decode_body(raw: bytes, content_type: str) -> Any:
    """JSON for APIs; plain text for CSV downloads (football-data.co.uk files are not always UTF-8)."""
    text = raw.decode("utf-8-sig", errors="strict") if _is_utf8(raw) else raw.decode("latin-1")
    if "json" in content_type or text.lstrip()[:1] in ("{", "["):
        return json.loads(text)
    return text


def _is_utf8(raw: bytes) -> bool:
    try:
        raw.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ApiClient:
    """One instance per provider. `budget` returns how many cost units may still be spent."""

    def __init__(
        self,
        provider: str,
        base_url: str,
        auth: dict[str, str],
        conn: sqlite3.Connection,
        transport: Transport,
        budget: Callable[[], int],
        auth_in_query: bool = False,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.auth_in_query = auth_in_query
        self.conn = conn
        self.transport = transport
        self.budget = budget
        self.sleep = sleep
        self.clock = clock

    def get(self, endpoint: str, params: dict[str, Any] | None = None, expected_cost: int = 1) -> HttpResponse:
        if self.budget() < expected_cost:
            self._log(endpoint, params, None, False, "budget exhausted (skipped)", None, 0)
            raise BudgetExceeded(f"{self.provider}: request budget exhausted, skipped {endpoint}")
        query = dict(params or {})
        headers: dict[str, str] = {}
        if self.auth_in_query:
            query.update(self.auth)
        else:
            headers.update(self.auth)
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if query:
            url += "?" + urllib.parse.urlencode(query)

        last_error = "unknown error"
        for attempt in range(3):
            try:
                resp = self.transport.get(url, headers)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_error = f"network: {e}"
                self.sleep(2**attempt)
                continue
            cost = _cost(self.provider, resp, expected_cost)
            remaining = _remaining(self.provider, resp)
            if resp.status == 429 or resp.status >= 500:
                last_error = f"HTTP {resp.status}"
                self._log(endpoint, params, resp.status, False, last_error, remaining, cost)
                self.sleep(2 ** (attempt + 1))
                continue
            if resp.status >= 400:
                msg = f"HTTP {resp.status}: {_err_text(resp.body)}"
                self._log(endpoint, params, resp.status, False, msg, remaining, cost)
                raise ProviderError(f"{self.provider} {endpoint}: {msg}")
            api_errors = _api_sports_errors(resp.body) if self.provider.startswith("api-") else None
            if api_errors:
                self._log(endpoint, params, resp.status, False, api_errors, remaining, cost)
                raise ProviderError(f"{self.provider} {endpoint}: {api_errors}")
            self._log(endpoint, params, resp.status, True, None, remaining, cost)
            return resp
        raise ProviderError(f"{self.provider} {endpoint}: {last_error} after retries")

    def _log(self, endpoint: str, params: dict[str, Any] | None, status: int | None, ok: bool, error: str | None, remaining: int | None, cost: int) -> None:
        safe = {k: v for k, v in (params or {}).items() if "key" not in k.lower()}
        self.conn.execute(
            "INSERT INTO provider_calls(provider, endpoint, params, http_status, ok, error, remaining, cost, called_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (self.provider, endpoint, json.dumps(safe), status, int(ok), error, remaining, cost, iso(self.clock())),
        )
        self.conn.commit()


def _cost(provider: str, resp: HttpResponse, expected: int) -> int:
    if provider == "the-odds-api":
        try:
            return int(resp.headers.get("x-requests-last", expected))
        except ValueError:
            return expected
    return 1


def _remaining(provider: str, resp: HttpResponse) -> int | None:
    key = "x-requests-remaining" if provider == "the-odds-api" else "x-ratelimit-requests-remaining"
    try:
        return int(float(resp.headers[key]))
    except (KeyError, ValueError):
        return None


def _api_sports_errors(body: Any) -> str | None:
    if not isinstance(body, dict):
        return "malformed response"
    errs = body.get("errors")
    if errs and (isinstance(errs, dict) and errs or isinstance(errs, list) and len(errs)):
        return json.dumps(errs, ensure_ascii=False)
    return None


def _err_text(body: Any) -> str:
    if isinstance(body, dict):
        return str(body.get("message") or body.get("errors") or body)[:200]
    return str(body)[:200]


# ---------- budgets ----------

def api_sports_budget(conn: sqlite3.Connection, provider: str, daily_limit: int, reserve: int, clock: Callable[[], datetime] = utcnow) -> Callable[[], int]:
    def remaining() -> int:
        day = clock().strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT COUNT(*) AS n, MIN(remaining) AS rem FROM provider_calls WHERE provider = ? AND substr(called_at,1,10) = ? AND http_status IS NOT NULL",
            (provider, day),
        ).fetchone()
        used_local = daily_limit - row["n"]
        reported = row["rem"] if row["rem"] is not None else daily_limit
        return min(used_local, reported) - reserve

    return remaining


def odds_budget(conn: sqlite3.Connection, monthly: int, clock: Callable[[], datetime] = utcnow) -> Callable[[], int]:
    """Credits allowed *today*: what's left this month spread evenly over the remaining days."""

    def remaining() -> int:
        now = clock()
        month = now.strftime("%Y-%m")
        row = conn.execute(
            "SELECT COALESCE(SUM(cost),0) AS used, MIN(remaining) AS rem FROM provider_calls WHERE provider = 'the-odds-api' AND substr(called_at,1,7) = ? AND http_status IS NOT NULL",
            (month,),
        ).fetchone()
        left = monthly - row["used"]
        if row["rem"] is not None:
            left = min(left, row["rem"])
        days_left = calendar.monthrange(now.year, now.month)[1] - now.day + 1
        used_today = conn.execute(
            "SELECT COALESCE(SUM(cost),0) AS u FROM provider_calls WHERE provider = 'the-odds-api' AND substr(called_at,1,10) = ? AND http_status IS NOT NULL",
            (now.strftime("%Y-%m-%d"),),
        ).fetchone()["u"]
        daily_share = (left + used_today) // max(1, days_left)
        return max(0, min(left, daily_share - used_today))

    return remaining
