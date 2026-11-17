"""football-data.org v4 adapter (free plan: current season, 10 requests/min, results may be delayed).

Covers Premier League (PL), La Liga (PD), Bundesliga (BL1) and Champions League (CL).
"""
from __future__ import annotations

from typing import Any

from .common import Fixture, TeamRef, parse_dt
from .http import ApiClient

BASE = "https://api.football-data.org/v4"

_STATUS = {
    **dict.fromkeys(["SCHEDULED", "TIMED"], "scheduled"),
    **dict.fromkeys(["IN_PLAY", "PAUSED", "EXTRA_TIME", "PENALTY_SHOOTOUT", "LIVE"], "live"),
    **dict.fromkeys(["FINISHED", "AWARDED"], "finished"),
    "POSTPONED": "postponed",
    "SUSPENDED": "postponed",
    "CANCELLED": "cancelled",
}


class FootballDataOrg:
    def __init__(self, client: ApiClient) -> None:
        self.c = client

    def matches(self, league_key: str, code: str, season: str) -> list[Fixture]:
        """All matches of the current season of competition `code` ('PL', 'PD', 'BL1', 'CL')."""
        body = self.c.get(f"competitions/{code}/matches").body
        out = []
        for m in (body or {}).get("matches", []) if isinstance(body, dict) else []:
            home, away = m.get("homeTeam") or {}, m.get("awayTeam") or {}
            if not home.get("id") or not away.get("id"):
                continue  # knockout slot without a team yet
            status = _STATUS.get(m.get("status", ""), "scheduled")
            hs, as_ = _regular_time_score(m.get("score") or {})
            if status != "finished":
                hs = as_ = None
            out.append(
                Fixture(
                    id=f"fb:fdo:{m['id']}",
                    sport="football",
                    league_key=league_key,
                    season=season,
                    home=_team(home),
                    away=_team(away),
                    kickoff=parse_dt(m["utcDate"]),
                    status=status,
                    home_score=hs,
                    away_score=as_,
                    venue=m.get("venue"),
                )
            )
        return out


def _team(t: dict[str, Any]) -> TeamRef:
    return TeamRef(id=f"fdo:{t['id']}", name=t.get("name") or t.get("shortName") or str(t["id"]), logo=t.get("crest"), short=t.get("tla"))


def _regular_time_score(score: dict[str, Any]) -> tuple[int | None, int | None]:
    """Bets settle on regular time. v4 'fullTime' includes extra time (and shoot-out goals) in cups."""
    for key in ("regularTime", "fullTime"):
        s = score.get(key) or {}
        if s.get("home") is not None and s.get("away") is not None:
            return int(s["home"]), int(s["away"])
    return None, None
