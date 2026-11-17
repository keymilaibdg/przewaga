"""Entry point used by GitHub Actions.

  python -m app.cli run --kind morning     # full daily update
  python -m app.cli run --kind afternoon   # optional second pass, only if the odds budget allows
  python -m app.cli status                 # print budgets and last run

Environment: APISPORTS_KEY, ODDS_API_KEY (GitHub Secrets). Missing keys => that provider is skipped.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from typing import Callable

from . import analysis, ingest, publish
from .config import (
    API_SPORTS_DAILY_LIMIT,
    API_SPORTS_RESERVE,
    DB_PATH,
    LEAGUES,
    ODDS_MARKETS,
    ODDS_MONTHLY_CREDITS,
    ODDS_REGIONS,
    PUBLISH_DIR,
    LeagueConfig,
    previous_season,
    season_for,
)
from .db import connect, dumps
from .providers.api_sports import BASKETBALL_BASE, FOOTBALL_BASE, ApiBasketball, ApiFootball
from .providers.http import ApiClient, BudgetExceeded, ProviderError, Transport, UrllibTransport, api_sports_budget, iso, odds_budget, utcnow
from .providers.odds_api import BASE as ODDS_BASE
from .providers.odds_api import OddsApi

log = logging.getLogger("przewaga")


class Pipeline:
    def __init__(self, conn: sqlite3.Connection, transport: Transport, keys: dict[str, str | None], clock: Callable[[], datetime] = utcnow) -> None:
        self.conn = conn
        self.clock = clock
        self.keys = keys
        self.errors: list[str] = []
        sk, ok = keys.get("apisports"), keys.get("odds")
        mk = lambda p, base: ApiClient(p, base, {"x-apisports-key": sk or ""}, conn, transport, api_sports_budget(conn, p, API_SPORTS_DAILY_LIMIT, API_SPORTS_RESERVE, clock), clock=clock)  # noqa: E731
        self.fb = ApiFootball(mk("api-football", FOOTBALL_BASE)) if sk else None
        self.bb = ApiBasketball(mk("api-basketball", BASKETBALL_BASE)) if sk else None
        self.odds = OddsApi(ApiClient("the-odds-api", ODDS_BASE, {"apiKey": ok or ""}, conn, transport, odds_budget(conn, ODDS_MONTHLY_CREDITS, clock), auth_in_query=True, clock=clock)) if ok else None

    # ---- helpers ----
    def _guard(self, label: str, fn: Callable[[], object]) -> object | None:
        try:
            return fn()
        except BudgetExceeded as e:
            self.errors.append(f"pominięto ({label}): {e}")
        except ProviderError as e:
            self.errors.append(f"błąd ({label}): {e}")
        except Exception as e:  # noqa: BLE001 - one failing league must not stop the run
            log.exception("unexpected error in %s", label)
            self.errors.append(f"błąd ({label}): {type(e).__name__}: {e}")
        return None

    def _league_id(self, lg: LeagueConfig, season: str) -> int | None:
        row = self.conn.execute("SELECT provider_id, season FROM leagues WHERE key = ?", (lg.key,)).fetchone()
        if row and row["provider_id"] and row["season"] == season:
            return row["provider_id"]
        api = self.fb if lg.sport == "football" else self.bb
        if api is None:
            return None
        pid = self._guard(f"liga {lg.key}", lambda: api.resolve_league(lg))
        if pid is not None:
            self.conn.execute(
                "INSERT INTO leagues(key, provider_id, season, resolved_at) VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET provider_id=excluded.provider_id, season=excluded.season, resolved_at=excluded.resolved_at",
                (lg.key, pid, season, iso(self.clock())),
            )
            self.conn.commit()
        return pid  # type: ignore[return-value]

    def _events_between(self, lg: LeagueConfig, start: datetime, end: datetime) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM events WHERE league_key = ? AND status = 'scheduled' AND kickoff BETWEEN ? AND ?",
            (lg.key, iso(start), iso(end)),
        ).fetchone()["n"]

    # ---- steps ----
    def fetch_fixtures(self, leagues: list[LeagueConfig], with_previous: bool) -> int:
        now, total = self.clock(), 0
        for lg in leagues:
            season = season_for(lg.sport, now)
            pid = self._league_id(lg, season)
            if pid is None:
                continue
            api = self.fb if lg.sport == "football" else self.bb
            fetch = (lambda s, lg=lg, pid=pid, api=api: api.fixtures(lg, pid, s)) if lg.sport == "football" else (lambda s, lg=lg, pid=pid, api=api: api.games(lg, pid, s))
            seasons = [season]
            if with_previous:
                prev = previous_season(lg.sport, season)
                have = self.conn.execute("SELECT COUNT(*) AS n FROM events WHERE league_key = ? AND season = ?", (lg.key, prev)).fetchone()["n"]
                if have == 0:
                    seasons.append(prev)
            for s in seasons:
                fx = self._guard(f"terminarz {lg.key} {s}", lambda s=s: fetch(s))
                if fx:
                    total += ingest.store_fixtures(self.conn, fx, now)  # type: ignore[arg-type]
        return total

    def fetch_injuries(self) -> int:
        if self.fb is None:
            return 0
        now, n = self.clock(), 0
        for lg in (x for x in LEAGUES if x.sport == "football"):
            pid = self._league_id(lg, season_for("football", now))
            for d in (0, 1):
                day = now + timedelta(days=d)
                start = day.replace(hour=0, minute=0, second=0, microsecond=0)
                if pid is None or self._events_between(lg, start, start + timedelta(days=1)) == 0:
                    continue
                items = self._guard(f"kontuzje {lg.key}", lambda pid=pid, day=day: self.fb.injuries(pid, season_for("football", now), day.strftime("%Y-%m-%d")))
                if items is not None:
                    n += ingest.store_injuries(self.conn, lg, items, now)  # type: ignore[arg-type]
        return n

    def fetch_odds(self, horizon_h: int) -> dict[str, int]:
        if self.odds is None:
            return {}
        now = self.clock()
        todo = [(lg, self._events_between(lg, now, now + timedelta(hours=horizon_h))) for lg in LEAGUES]
        todo = sorted([t for t in todo if t[1] > 0], key=lambda t: -t[1])
        out: dict[str, int] = {}
        for lg, _ in todo:
            evs = self._guard(f"kursy {lg.key}", lambda lg=lg: self.odds.odds(lg.odds_key, ODDS_MARKETS[lg.sport], ODDS_REGIONS))
            if evs is not None:
                out[lg.key] = ingest.store_odds(self.conn, lg, evs, now)["matched"]  # type: ignore[arg-type]
        return out

    def analyse_and_publish(self, run_kind: str) -> dict[str, object]:
        now = self.clock()
        settled = analysis.settle(self.conn, now)
        models = analysis.fit_models(self.conn, now)
        stats = {"new": 0, "updated": 0, "withdrawn": 0}
        analyses = []
        for ev in analysis.upcoming_events(self.conn, now):
            a = analysis.analyse_event(self.conn, ev, models.get(ev["league_key"]), now)
            for k, v in analysis.sync_recommendations(self.conn, a, now).items():
                stats[k] += v
            analyses.append(a)
        configured = {"api-football": bool(self.fb), "api-basketball": bool(self.bb), "the-odds-api": bool(self.odds)}
        written = publish.write_all(self.conn, analyses, now, PUBLISH_DIR, configured, run_kind)
        return {"settled": settled, **stats, **written}

    def run(self, kind: str) -> dict[str, object]:
        started = self.clock()
        run_id = self.conn.execute("INSERT INTO runs(kind, started_at) VALUES (?, ?)", (kind, iso(started))).lastrowid
        self.conn.commit()
        if kind == "morning":
            fixtures = self.fetch_fixtures(list(LEAGUES), with_previous=True)
            injuries = self.fetch_injuries()
            odds = self.fetch_odds(horizon_h=36)
        else:
            today = [lg for lg in LEAGUES if self._events_between(lg, started - timedelta(hours=14), started + timedelta(hours=12))]
            fixtures = self.fetch_fixtures(today, with_previous=False)
            injuries = 0
            odds = self.fetch_odds(horizon_h=10)
        result = self.analyse_and_publish(kind)
        summary = {"fixtures": fixtures, "injuries": injuries, "odds_matched": odds, **result, "errors": self.errors}
        self.conn.execute("UPDATE runs SET finished_at = ?, ok = ?, summary = ? WHERE id = ?", (iso(self.clock()), int(not self.errors), dumps(summary), run_id))
        self.conn.commit()
        return summary


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="przewaga")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--kind", choices=["morning", "afternoon"], default="morning")
    sub.add_parser("status")
    args = p.parse_args(argv)

    conn = connect(DB_PATH)
    keys = {"apisports": os.environ.get("APISPORTS_KEY") or None, "odds": os.environ.get("ODDS_API_KEY") or None}
    pipe = Pipeline(conn, UrllibTransport(), keys)
    if args.cmd == "status":
        now = utcnow()
        print(json.dumps({
            "odds_credits_today": odds_budget(conn, ODDS_MONTHLY_CREDITS)(),
            "api_football_left_today": api_sports_budget(conn, "api-football", API_SPORTS_DAILY_LIMIT, API_SPORTS_RESERVE)(),
            "api_basketball_left_today": api_sports_budget(conn, "api-basketball", API_SPORTS_DAILY_LIMIT, API_SPORTS_RESERVE)(),
            "last_run": dict(conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone() or {}),
            "now": iso(now),
        }, ensure_ascii=False, indent=2, default=str))
        return 0
    if not any(keys.values()):
        log.warning("Brak kluczy API (APISPORTS_KEY / ODDS_API_KEY) — publikuję tylko dane już zapisane w bazie.")
    summary = pipe.run(args.kind)
    conn.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0  # provider errors are reported in summary/meta, the run itself succeeded


if __name__ == "__main__":
    sys.exit(main())
