"""Static configuration: covered competitions, thresholds, request budgets."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("PRZEWAGA_DB", ROOT / "pipeline" / "data" / "przewaga.sqlite3"))
PUBLISH_DIR = Path(os.environ.get("PRZEWAGA_PUBLISH_DIR", ROOT / "frontend" / "public" / "data"))


@dataclass(frozen=True)
class LeagueConfig:
    key: str
    name: str  # Polish display name
    sport: str  # "football" | "basketball"
    country: str  # provider country name used for ID resolution
    search: str  # provider league name used for ID resolution
    odds_key: str  # The Odds API sport key
    known_id: int | None = None  # sanity hint; the ID is always verified at runtime


LEAGUES: tuple[LeagueConfig, ...] = (
    LeagueConfig("epl", "Premier League", "football", "England", "Premier League", "soccer_epl", 39),
    LeagueConfig("laliga", "La Liga", "football", "Spain", "La Liga", "soccer_spain_la_liga", 140),
    LeagueConfig("bundesliga", "Bundesliga", "football", "Germany", "Bundesliga", "soccer_germany_bundesliga", 78),
    LeagueConfig("ucl", "Liga Mistrzów", "football", "World", "UEFA Champions League", "soccer_uefa_champs_league", 2),
    LeagueConfig("uel", "Liga Europy", "football", "World", "UEFA Europa League", "soccer_uefa_europa_league", 3),
    LeagueConfig("ekstraklasa", "Ekstraklasa", "football", "Poland", "Ekstraklasa", "soccer_poland_ekstraklasa", 106),
    LeagueConfig("nba", "NBA", "basketball", "USA", "NBA", "basketball_nba", None),
    LeagueConfig("euroleague", "Euroliga", "basketball", "Europe", "Euroleague", "basketball_euroleague", None),
)

LEAGUE_BY_KEY = {lg.key: lg for lg in LEAGUES}

# ---- recommendation gate (engine) ----
MIN_EV = 0.02
MIN_QUALITY = 60
MAX_PRICE = 5.0
# Weight of the model vs the de-vigged market when forming the final probability (shrinkage).
MODEL_WEIGHT = 0.5
# Odds older than this (hours) are stale: no new recommendations from them.
MAX_ODDS_AGE_H = 14
# If the raw model disagrees with the de-vigged market by more than this, the model is probably missing
# information (injury, rotation, lineup news): never recommend, flag instead.
MAX_DISAGREEMENT = 0.12

# ---- request budgets (free plans) ----
API_SPORTS_DAILY_LIMIT = 100  # per API (football, basketball) per day
API_SPORTS_RESERVE = 10  # never spend the last N requests
ODDS_MONTHLY_CREDITS = 500
ODDS_REGIONS = "eu"
ODDS_MARKETS = {"football": "h2h,totals", "basketball": "h2h,spreads,totals"}

HORIZON_DAYS = 7


def season_for(sport: str, when: datetime) -> str:
    """Provider season identifier for a date. Football: '2026'; basketball: '2026-2027'."""
    start = when.year if when.month >= 7 else when.year - 1
    return str(start) if sport == "football" else f"{start}-{start + 1}"


def previous_season(sport: str, season: str) -> str:
    start = int(season[:4]) - 1
    return str(start) if sport == "football" else f"{start}-{start + 1}"
