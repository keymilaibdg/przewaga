"""balldontlie NBA adapter (free plan: teams, players, games; 5 requests/min).

GET /v1/games?seasons[]=2025&per_page=100&cursor=... ; header `Authorization: <key>`.
A full season is ~13 pages, so it is downloaded once and then refreshed incrementally by date range.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from .common import Fixture, TeamRef, parse_dt
from .http import ApiClient

BASE = "https://api.balldontlie.io/v1"
PAGE_PAUSE_S = 13  # 5 requests/min
MAX_PAGES = 30


def season_year(season: str) -> int:
    """'2025-2026' -> 2025 (balldontlie labels a season by its start year)."""
    return int(season[:4])


class Balldontlie:
    def __init__(self, client: ApiClient) -> None:
        self.c = client

    def games(self, league_key: str, season: str, start: date | None = None, end: date | None = None) -> list[Fixture]:
        params: dict[str, Any] = {"seasons[]": season_year(season), "per_page": 100}
        if start:
            params["start_date"] = start.isoformat()
        if end:
            params["end_date"] = end.isoformat()
        out: list[Fixture] = []
        cursor = None
        for page in range(MAX_PAGES):
            if page:
                self.c.sleep(PAGE_PAUSE_S)
            body = self.c.get("games", {**params, **({"cursor": cursor} if cursor else {})}).body or {}
            out += [f for g in body.get("data", []) if (f := _fixture(g, league_key, season))]
            cursor = (body.get("meta") or {}).get("next_cursor")
            if not cursor:
                break
        return out


def _fixture(g: dict[str, Any], league_key: str, season: str) -> Fixture | None:
    h, v = g.get("home_team") or {}, g.get("visitor_team") or {}
    if not h.get("id") or not v.get("id"):
        return None
    status = _status(str(g.get("status") or ""))
    finished = status == "finished"
    return Fixture(
        id=f"bb:bdl:{g['id']}",
        sport="basketball",
        league_key=league_key,
        season=season,
        home=TeamRef(f"bdl:{h['id']}", h.get("full_name") or h.get("name") or str(h["id"]), short=h.get("abbreviation")),
        away=TeamRef(f"bdl:{v['id']}", v.get("full_name") or v.get("name") or str(v["id"]), short=v.get("abbreviation")),
        kickoff=_tipoff(g),
        status=status,
        home_score=g.get("home_team_score") if finished else None,
        away_score=g.get("visitor_team_score") if finished else None,
        venue=None,
    )


def _status(s: str) -> str:
    low = s.lower()
    if low.startswith("final"):
        return "finished"
    if "postpon" in low:
        return "postponed"
    if "cancel" in low:
        return "cancelled"
    if _iso(s) or low.endswith(" et") or not s:
        return "scheduled"  # before tip-off the status is the start time ('2026-11-18T00:30:00Z' / '7:30 pm ET')
    return "live"  # '1st Qtr', 'Halftime', 'OT'


def _iso(s: str) -> datetime | None:
    if "T" not in s:
        return None  # a bare date is not a tip-off time
    try:
        d = parse_dt(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _tipoff(g: dict[str, Any]) -> datetime:
    for k in ("datetime", "status"):
        d = _iso(str(g.get(k) or ""))
        if d:
            return d.astimezone(timezone.utc)
    # Date only (US Eastern): most games tip off around 00:00-03:00 UTC the next day.
    day = datetime.fromisoformat(str(g["date"])[:10]).replace(tzinfo=timezone.utc)
    return day + timedelta(hours=23, minutes=30)
