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
    country: str  # display country / region
    odds_key: str  # The Odds API sport key
    # Where upcoming fixtures and results come from:
    #   "fdo"  football-data.org (fixtures + results, current season)
    #   "bdl"  balldontlie (NBA games + results)
    #   "odds" The Odds API: /events (free) for fixtures, /scores (2 credits) for results
    fixtures_source: str
    fdo_code: str | None = None  # football-data.org competition code
    csv_file: str | None = None  # football-data.co.uk history: 'E0' (per-season file) or 'new/POL' (all seasons)
    # Cups and the Euroleague: too little shared history in free sources -> show odds, never recommend (ETAP 5).
    recommend: bool = True
    # API-SPORTS lookup, used only by backtests on seasons 2022-2024 (the free plan has no current seasons).
    search: str = ""
    known_id: int | None = None


LEAGUES: tuple[LeagueConfig, ...] = (
    LeagueConfig("epl", "Premier League", "football", "England", "soccer_epl", "fdo", "PL", "E0", search="Premier League", known_id=39),
    LeagueConfig("laliga", "La Liga", "football", "Spain", "soccer_spain_la_liga", "fdo", "PD", "SP1", search="La Liga", known_id=140),
    LeagueConfig("bundesliga", "Bundesliga", "football", "Germany", "soccer_germany_bundesliga", "fdo", "BL1", "D1", search="Bundesliga", known_id=78),
    LeagueConfig("ucl", "Liga Mistrzów", "football", "Europe", "soccer_uefa_champs_league", "fdo", "CL", recommend=False, search="UEFA Champions League", known_id=2),
    LeagueConfig("uel", "Liga Europy", "football", "Europe", "soccer_uefa_europa_league", "odds", recommend=False, search="UEFA Europa League", known_id=3),
    LeagueConfig("ekstraklasa", "Ekstraklasa", "football", "Poland", "soccer_poland_ekstraklasa", "odds", csv_file="new/POL", search="Ekstraklasa", known_id=106),
    LeagueConfig("nba", "NBA", "basketball", "USA", "basketball_nba", "bdl", search="NBA"),
    LeagueConfig("euroleague", "Euroliga", "basketball", "Europe", "basketball_euroleague", "odds", recommend=False, search="Euroleague"),
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
API_SPORTS_DAILY_LIMIT = 100  # per API (football, basketball) per day (backtests only)
API_SPORTS_RESERVE = 10  # never spend the last N requests
FDO_DAILY_LIMIT = 60  # football-data.org: 10/min, no daily cap; we need ~4 calls per run
CSV_DAILY_LIMIT = 20  # football-data.co.uk: 4-7 files per day
BDL_DAILY_LIMIT = 80  # balldontlie: 5/min; a full season is ~13 pages
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
