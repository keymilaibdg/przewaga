"""Schedule context of a basketball game: rest days, back-to-back, travel between arenas.

Computed only from the fixture list (free: balldontlie / archive), so it costs no API calls. The ratings model
uses it when the backtest shows it helps (calibration.json: fatigue); the analysis screen always shows it.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime

# NBA arenas (approximate coordinates), keyed by team abbreviation.
ARENAS: dict[str, tuple[float, float]] = {
    "ATL": (33.757, -84.396), "BOS": (42.366, -71.062), "BKN": (40.683, -73.976), "CHA": (35.225, -80.839),
    "CHI": (41.881, -87.674), "CLE": (41.496, -81.688), "DAL": (32.790, -96.810), "DEN": (39.749, -105.008),
    "DET": (42.341, -83.055), "GSW": (37.768, -122.388), "HOU": (29.751, -95.362), "IND": (39.764, -86.155),
    "LAC": (33.945, -118.341), "LAL": (34.043, -118.267), "MEM": (35.138, -90.051), "MIA": (25.781, -80.188),
    "MIL": (43.045, -87.917), "MIN": (44.979, -93.276), "NOP": (29.949, -90.082), "NYK": (40.751, -73.993),
    "OKC": (35.463, -97.515), "ORL": (28.539, -81.384), "PHI": (39.901, -75.172), "PHX": (33.446, -112.071),
    "POR": (45.532, -122.667), "SAC": (38.580, -121.500), "SAS": (29.427, -98.437), "TOR": (43.643, -79.379),
    "UTA": (40.768, -111.901), "WAS": (38.898, -77.021),
}

# Team nickname (last word of the full name) -> abbreviation, for names from balldontlie / The Odds API.
NICKNAMES = {
    "hawks": "ATL", "celtics": "BOS", "nets": "BKN", "hornets": "CHA", "bulls": "CHI", "cavaliers": "CLE", "mavericks": "DAL",
    "nuggets": "DEN", "pistons": "DET", "warriors": "GSW", "rockets": "HOU", "pacers": "IND", "clippers": "LAC", "lakers": "LAL",
    "grizzlies": "MEM", "heat": "MIA", "bucks": "MIL", "timberwolves": "MIN", "pelicans": "NOP", "knicks": "NYK", "thunder": "OKC",
    "magic": "ORL", "76ers": "PHI", "sixers": "PHI", "suns": "PHX", "blazers": "POR", "kings": "SAC", "spurs": "SAS", "raptors": "TOR",
    "jazz": "UTA", "wizards": "WAS",
}

REST_CAP = 3.0
B2B_HOURS = 36.0  # consecutive days (kickoffs < 36 h apart)


def nba_abbr(name: str) -> str | None:
    """'Cleveland Cavaliers' -> 'CLE'; abbreviations pass through."""
    if name.upper() in ARENAS:
        return name.upper()
    words = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    return next((NICKNAMES[w] for w in reversed(words) if w in NICKNAMES), None)


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


@dataclass(frozen=True)
class TeamCtx:
    rest_days: float  # days since the previous game (capped at REST_CAP; season opener = REST_CAP)
    b2b: bool  # played the day before
    travel_km: float  # from the previous game's arena to this one
    games_last_7d: int  # games in the 7 days before this one


@dataclass(frozen=True)
class GameCtx:
    home: TeamCtx
    away: TeamCtx

    def features(self) -> tuple[float, float, float, float]:
        """Margin features: rest difference, home b2b, away b2b, travel difference (1000 km, away minus home)."""
        return (
            min(self.home.rest_days, REST_CAP) - min(self.away.rest_days, REST_CAP),
            float(self.home.b2b),
            float(self.away.b2b),
            (self.away.travel_km - self.home.travel_km) / 1000.0,
        )


NEUTRAL = GameCtx(TeamCtx(REST_CAP, False, 0.0, 0), TeamCtx(REST_CAP, False, 0.0, 0))


def contexts(games: list[tuple[str, datetime, str, str, str]]) -> dict[str, GameCtx]:
    """games: (key, kickoff UTC, home team id, away team id, home team name) incl. scheduled ones.

    The home team's name locates the arena. Only earlier games of the same team are used, so the context is
    known before tip-off (no leakage).
    """
    last: dict[str, tuple[datetime, str | None]] = {}
    recent: dict[str, list[datetime]] = {}
    out: dict[str, GameCtx] = {}
    for key, ko, home, away, home_name in sorted(games, key=lambda g: g[1]):
        venue = nba_abbr(home_name)
        ctx = []
        for team in (home, away):
            prev = last.get(team)
            hist = [d for d in recent.get(team, []) if 0 < (ko - d).total_seconds() <= 7 * 86400]
            if prev is None or (ko - prev[0]).days > 30:
                ctx.append(TeamCtx(REST_CAP, False, 0.0, len(hist)))
            else:
                gap_h = (ko - prev[0]).total_seconds() / 3600
                rest = min(REST_CAP, max(0.0, round(gap_h / 24 - 1, 1)))  # nights off between games
                a, b = ARENAS.get(prev[1] or ""), ARENAS.get(venue or "")
                ctx.append(TeamCtx(rest, gap_h < B2B_HOURS, km(a, b) if a and b else 0.0, len(hist)))
        out[key] = GameCtx(ctx[0], ctx[1])
        for team in (home, away):
            last[team] = (ko, venue)
            recent.setdefault(team, []).append(ko)
    return out
