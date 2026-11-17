"""The Odds API (v4) adapter."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .http import ApiClient

BASE = "https://api.the-odds-api.com/v4"

MARKET_COST = {"h2h": 1, "spreads": 1, "totals": 1}


@dataclass
class OddsQuote:
    bookmaker: str
    bookmaker_title: str
    market: str  # h2h | totals | spreads
    outcome_name: str  # team name | Draw | Over | Under
    point: float | None
    price: float
    updated_at: str | None


@dataclass
class OddsEvent:
    id: str
    sport_key: str
    commence_time: datetime
    home_team: str
    away_team: str
    quotes: list[OddsQuote]


class OddsApi:
    def __init__(self, client: ApiClient) -> None:
        self.c = client
        self.extras = OddsApiExtras(client)

    def events(self, sport_key: str) -> list[OddsEvent]:
        return self.extras.events(sport_key)

    def scores(self, sport_key: str, days_from: int = 3) -> list[OddsScore]:
        return self.extras.scores(sport_key, days_from)

    @staticmethod
    def cost(markets: str, regions: str) -> int:
        return len(markets.split(",")) * len(regions.split(","))

    def odds(self, sport_key: str, markets: str, regions: str) -> list[OddsEvent]:
        params = {"regions": regions, "markets": markets, "oddsFormat": "decimal", "dateFormat": "iso"}
        body = self.c.get(f"sports/{sport_key}/odds", params, expected_cost=self.cost(markets, regions)).body
        events = []
        for e in body if isinstance(body, list) else []:
            quotes = [
                OddsQuote(
                    bookmaker=b["key"],
                    bookmaker_title=b.get("title", b["key"]),
                    market=m["key"],
                    outcome_name=o["name"],
                    point=o.get("point"),
                    price=float(o["price"]),
                    updated_at=m.get("last_update") or b.get("last_update"),
                )
                for b in e.get("bookmakers", [])
                for m in b.get("markets", [])
                for o in m.get("outcomes", [])
                if o.get("price") and float(o["price"]) > 1.0
            ]
            events.append(
                OddsEvent(
                    id=e["id"],
                    sport_key=e["sport_key"],
                    commence_time=datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")),
                    home_team=e["home_team"],
                    away_team=e["away_team"],
                    quotes=quotes,
                )
            )
        return events


@dataclass
class OddsScore:
    id: str
    sport_key: str
    commence_time: datetime
    home_team: str
    away_team: str
    completed: bool
    home_score: int | None
    away_score: int | None


class OddsApiExtras:
    """Endpoints used as a fixtures/results source for leagues without a free fixtures API."""

    def __init__(self, client: ApiClient) -> None:
        self.c = client

    def events(self, sport_key: str) -> list[OddsEvent]:
        """Upcoming events without odds. Free: does not count against the monthly quota."""
        body = self.c.get(f"sports/{sport_key}/events", {"dateFormat": "iso"}, expected_cost=0).body
        return [
            OddsEvent(id=e["id"], sport_key=e["sport_key"], commence_time=_dt(e["commence_time"]), home_team=e["home_team"], away_team=e["away_team"], quotes=[])
            for e in (body if isinstance(body, list) else [])
        ]

    def scores(self, sport_key: str, days_from: int = 3) -> list[OddsScore]:
        """Results of the last `days_from` days (costs 2 credits with daysFrom)."""
        body = self.c.get(f"sports/{sport_key}/scores", {"daysFrom": days_from, "dateFormat": "iso"}, expected_cost=2).body
        out = []
        for e in body if isinstance(body, list) else []:
            by_name = {s.get("name"): _score(s.get("score")) for s in (e.get("scores") or [])}
            out.append(
                OddsScore(
                    id=e["id"],
                    sport_key=e["sport_key"],
                    commence_time=_dt(e["commence_time"]),
                    home_team=e["home_team"],
                    away_team=e["away_team"],
                    completed=bool(e.get("completed")),
                    home_score=by_name.get(e["home_team"]),
                    away_score=by_name.get(e["away_team"]),
                )
            )
        return out


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _score(v: object) -> int | None:
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return None
