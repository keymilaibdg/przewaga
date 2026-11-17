"""API-SPORTS adapters: API-Football (v3) and API-Basketball (v1). One free key covers both."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..config import LeagueConfig
from .http import ApiClient, ProviderError

FOOTBALL_BASE = "https://v3.football.api-sports.io"
BASKETBALL_BASE = "https://v1.basketball.api-sports.io"

_FB_STATUS = {
    **dict.fromkeys(["TBD", "NS"], "scheduled"),
    **dict.fromkeys(["1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"], "live"),
    **dict.fromkeys(["FT", "AET", "PEN"], "finished"),
    "PST": "postponed",
    **dict.fromkeys(["CANC", "ABD", "AWD", "WO"], "cancelled"),
}
_BB_STATUS = {
    "NS": "scheduled",
    **dict.fromkeys(["Q1", "Q2", "Q3", "Q4", "OT", "BT", "HT"], "live"),
    **dict.fromkeys(["FT", "AOT"], "finished"),
    "POST": "postponed",
    **dict.fromkeys(["CANC", "SUSP", "AWD", "ABD"], "cancelled"),
}


@dataclass
class TeamRef:
    id: str
    name: str
    logo: str | None


@dataclass
class Fixture:
    id: str
    sport: str
    league_key: str
    season: str
    home: TeamRef
    away: TeamRef
    kickoff: datetime
    status: str
    home_score: int | None
    away_score: int | None
    venue: str | None


@dataclass
class Injury:
    team_id: str
    player: str
    kind: str | None
    reason: str | None
    fixture_id: str | None


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class ApiFootball:
    def __init__(self, client: ApiClient) -> None:
        self.c = client

    def resolve_league(self, lg: LeagueConfig) -> int:
        body = self.c.get("leagues", {"name": lg.search, "country": lg.country}).body
        cands = [r for r in body.get("response", []) if r["league"]["name"].lower() == lg.search.lower()]
        if not cands:
            raise ProviderError(f"API-Football: league not found: {lg.search} ({lg.country})")
        ids = [c["league"]["id"] for c in cands]
        return lg.known_id if lg.known_id in ids else ids[0]

    def fixtures(self, lg: LeagueConfig, league_id: int, season: str) -> list[Fixture]:
        body = self.c.get("fixtures", {"league": league_id, "season": season}).body
        out = []
        for r in body.get("response", []):
            f, t = r["fixture"], r["teams"]
            # Bets settle on regular time: prefer the 90-minute score when extra time was played.
            ft = (r.get("score") or {}).get("fulltime") or {}
            hs = ft.get("home") if ft.get("home") is not None else r["goals"]["home"]
            as_ = ft.get("away") if ft.get("away") is not None else r["goals"]["away"]
            out.append(
                Fixture(
                    id=f"fb:af:{f['id']}",
                    sport="football",
                    league_key=lg.key,
                    season=season,
                    home=TeamRef(f"af:{t['home']['id']}", t["home"]["name"], t["home"].get("logo")),
                    away=TeamRef(f"af:{t['away']['id']}", t["away"]["name"], t["away"].get("logo")),
                    kickoff=_dt(f["date"]),
                    status=_FB_STATUS.get(f["status"]["short"], "scheduled"),
                    home_score=hs,
                    away_score=as_,
                    venue=(f.get("venue") or {}).get("name"),
                )
            )
        return out

    def injuries(self, league_id: int, season: str, date: str) -> list[Injury]:
        body = self.c.get("injuries", {"league": league_id, "season": season, "date": date}).body
        return [
            Injury(
                team_id=f"af:{r['team']['id']}",
                player=r["player"]["name"],
                kind=r["player"].get("type"),
                reason=r["player"].get("reason"),
                fixture_id=f"fb:af:{r['fixture']['id']}" if r.get("fixture") else None,
            )
            for r in body.get("response", [])
        ]


class ApiBasketball:
    def __init__(self, client: ApiClient) -> None:
        self.c = client

    def resolve_league(self, lg: LeagueConfig) -> int:
        body = self.c.get("leagues", {"search": lg.search}).body
        resp = body.get("response", [])
        exact = [r for r in resp if r["name"].lower() == lg.search.lower()]
        by_country = [r for r in exact if (r.get("country") or {}).get("name", "").lower() == lg.country.lower()]
        pick = (by_country or exact)
        if not pick:
            raise ProviderError(f"API-Basketball: league not found: {lg.search} ({lg.country})")
        return pick[0]["id"]

    def games(self, lg: LeagueConfig, league_id: int, season: str) -> list[Fixture]:
        body = self.c.get("games", {"league": league_id, "season": season}).body
        out = []
        for r in body.get("response", []):
            t, sc = r["teams"], r.get("scores") or {}
            out.append(
                Fixture(
                    id=f"bb:ab:{r['id']}",
                    sport="basketball",
                    league_key=lg.key,
                    season=season,
                    home=TeamRef(f"ab:{t['home']['id']}", t["home"]["name"], t["home"].get("logo")),
                    away=TeamRef(f"ab:{t['away']['id']}", t["away"]["name"], t["away"].get("logo")),
                    kickoff=_dt(r["date"]),
                    status=_BB_STATUS.get(r["status"]["short"], "scheduled"),
                    home_score=(sc.get("home") or {}).get("total"),
                    away_score=(sc.get("away") or {}).get("total"),
                    venue=None,
                )
            )
        return out


def body_list(body: Any) -> list[Any]:
    return body if isinstance(body, list) else []
