"""football-data.co.uk CSV results (no key). Training history for the football model.

Main leagues: one file per season, e.g. mmz4281/2526/E0.csv (columns Date, Time, HomeTeam, AwayTeam, FTHG, FTAG).
Extra leagues (Ekstraklasa): one file with all seasons, new/POL.csv (columns Season, Date, Time, Home, Away, HG, AG).
Dates are dd/mm/yyyy (older files dd/mm/yy), times are UK local time and may be missing.
Both formats also carry Pinnacle closing odds (PSCH/PSCD/PSCA), useful for the ETAP 5 backtest.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..config import season_for
from .common import Fixture, TeamRef
from .http import ApiClient, ProviderError

BASE = "https://www.football-data.co.uk"
UK = ZoneInfo("Europe/London")


def season_code(season: str) -> str:
    """'2025' (2025/26) -> '2526'."""
    y = int(season[:4])
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


class FootballDataCsv:
    def __init__(self, client: ApiClient) -> None:
        self.c = client

    def results(self, league_key: str, file: str, seasons: list[str]) -> list[Fixture]:
        """Finished matches of `seasons`. `file`: 'E0' (one file per season) or 'new/POL' (all seasons)."""
        if file.startswith("new/"):
            return parse(self._text(f"{file}.csv"), league_key, set(seasons))
        out: list[Fixture] = []
        for s in seasons:
            out += parse(self._text(f"mmz4281/{season_code(s)}/{file}.csv"), league_key, {s})
        return out

    def _text(self, path: str) -> str:
        body = self.c.get(path).body
        if not isinstance(body, str):
            raise ProviderError(f"football-data.co.uk {path}: expected CSV, got {type(body).__name__}")
        return body


def parse(text: str, league_key: str, seasons: set[str]) -> list[Fixture]:
    from ..teams import slug

    out = []
    for row in csv.DictReader(io.StringIO(text)):
        home = (row.get("HomeTeam") or row.get("Home") or "").strip()
        away = (row.get("AwayTeam") or row.get("Away") or "").strip()
        hg, ag = _int(row.get("FTHG", row.get("HG"))), _int(row.get("FTAG", row.get("AG")))
        ko = _kickoff(row.get("Date", ""), row.get("Time", ""))
        if not home or not away or hg is None or ag is None or ko is None:
            continue  # blank trailing lines, unplayed matches
        season = season_for("football", ko)
        if season not in seasons:
            continue
        out.append(
            Fixture(
                id=f"fb:csv:{league_key}:{ko.date().isoformat()}:{slug(home)}:{slug(away)}",
                sport="football",
                league_key=league_key,
                season=season,
                home=TeamRef(None, home),
                away=TeamRef(None, away),
                kickoff=ko,
                status="finished",
                home_score=hg,
                away_score=ag,
                venue=None,
            )
        )
    return out


def _int(v: str | None) -> int | None:
    try:
        return int(float(v)) if v not in (None, "") else None
    except ValueError:
        return None


def _kickoff(date: str, time: str) -> datetime | None:
    date = date.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            d = datetime.strptime(date, fmt)
            break
        except ValueError:
            continue
    else:
        return None
    hh, mm = 15, 0  # no time in older files: assume a 15:00 kickoff
    if time and ":" in time:
        try:
            hh, mm = (int(x) for x in time.strip().split(":")[:2])
        except ValueError:
            pass
    return d.replace(hour=hh, minute=mm, tzinfo=UK).astimezone(timezone.utc)
