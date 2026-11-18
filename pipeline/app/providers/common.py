"""Provider-neutral data shapes shared by all adapters."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TeamRef:
    id: str | None  # provider-native id ('fdo:64', 'bdl:2'); None when the source has names only (CSV, odds)
    name: str
    logo: str | None = None
    short: str | None = None  # 3-letter code if the provider has one


@dataclass
class Fixture:
    id: str
    sport: str
    league_key: str
    season: str
    home: TeamRef
    away: TeamRef
    kickoff: datetime
    status: str  # scheduled | live | finished | postponed | cancelled
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


def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
