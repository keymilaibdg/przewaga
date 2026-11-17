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
