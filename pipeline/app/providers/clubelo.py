"""ClubElo (clubelo.com): free Elo ratings of European clubs, recalculated after every round.

CSV API: http://api.clubelo.com/YYYY-MM-DD -> Rank,Club,Country,Level,Elo,From,To (one call returns every club).
The ratings are an independent strength estimate shown next to our model in the price insight.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime

BASE = "http://api.clubelo.com/"
# Our leagues -> ClubElo country codes (cups: any country)
LEAGUE_COUNTRY = {"epl": "ENG", "laliga": "ESP", "bundesliga": "GER", "ekstraklasa": "POL"}


@dataclass
class EloRow:
    rank: int | None
    club: str
    country: str
    level: int | None
    elo: float


def url_for(day: datetime) -> str:
    return f"{BASE}{day.strftime('%Y-%m-%d')}"


def parse(text: str) -> list[EloRow]:
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            elo = float(r.get("Elo") or "")
        except ValueError:
            continue
        rank = r.get("Rank") or ""
        level = r.get("Level") or ""
        out.append(EloRow(int(rank) if rank.isdigit() else None, (r.get("Club") or "").strip(), (r.get("Country") or "").strip(), int(level) if level.isdigit() else None, elo))
    return [x for x in out if x.club]
