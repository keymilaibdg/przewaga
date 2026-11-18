"""Data for the cross-league cup ratings: domestic leagues + UEFA cup matches, all mapped to one team key space."""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..config import season_for
from ..models import cups as cm
from .data import CupMatch, FbMatch, SourceError, fd_extra, fd_season

log = logging.getLogger("przewaga.backtest")

MAIN_CODES = ("E0", "E1", "SC0", "D1", "I1", "SP1", "F1", "N1", "B1", "P1", "T1", "G1")
EXTRA_CODES = ("AUT", "DNK", "NOR", "SWE", "SWZ", "POL", "ROU", "IRL", "FIN")
YEARS = 4  # history used for the ratings


@dataclass
class Dataset:
    matches: list[tuple[datetime, cm.GMatch]]  # (kickoff, match with days_ago=0; set at fit time)
    entries: dict[str, dict]  # key -> {"name", "aliases", "country"}
    cup_rows: list[tuple[datetime, str, str, int, int, bool]]  # kickoff, home key, away key, hg, ag, neutral
    skipped: list[str]


def domestic(now: datetime, offline: bool = False) -> tuple[list[FbMatch], list[str]]:
    out, skipped = [], []
    cur = int(season_for("football", now))
    for code in MAIN_CODES:
        for y in range(cur - YEARS, cur + 1):
            try:
                out += fd_season(code, y, code, cur, offline=offline)
            except SourceError as e:
                skipped.append(f"{code} {y}: {e}")
    for code in EXTRA_CODES:
        try:
            out += [m for m in fd_extra(code, code, offline=offline) if m.kickoff >= now - timedelta(days=365 * YEARS + 120)]
        except SourceError as e:
            skipped.append(f"{code}: {e}")
    return out, skipped


def build(now: datetime, cup_matches: list[CupMatch], db: sqlite3.Connection | None = None, offline: bool = False) -> Dataset:
    dom, skipped = domestic(now, offline)
    entries: dict[str, dict] = {}
    matches: list[tuple[datetime, cm.GMatch]] = []
    for m in dom:
        cc = cm.FD_COUNTRY[m.league]
        hk, ak = f"{cc}:{m.home}", f"{cc}:{m.away}"
        for k, nm in ((hk, m.home), (ak, m.away)):
            entries.setdefault(k, {"name": nm, "aliases": [], "country": cc})
        matches.append((m.kickoff, cm.GMatch(hk, ak, m.hg, m.ag, 0.0, m.league)))

    def key_for(name: str, country: str | None) -> str:
        cc = cm.AF_COUNTRY.get(country or "", None)
        if cc:
            k = cm.find_key(name, entries, cc)
            if k:
                if name != entries[k]["name"] and name not in entries[k]["aliases"]:
                    entries[k]["aliases"].append(name)
                return k
        k = f"{cc or (country or 'XX')}:{name}"
        entries.setdefault(k, {"name": name, "aliases": [], "country": cc or country})
        return k

    cup_rows = []
    for c in cup_matches:
        hk, ak = key_for(c.home, c.home_country), key_for(c.away, c.away_country)
        cup_rows.append((c.kickoff, hk, ak, c.hg, c.ag, c.neutral))
    if db is not None:  # current season from the live database (Champions League from football-data.org, Europa League from /scores)
        rows = db.execute(
            """SELECT e.kickoff, e.home_score, e.away_score, e.home_team_id, e.away_team_id, h.name AS hn, w.name AS an FROM events e
               JOIN teams h ON h.id = e.home_team_id JOIN teams w ON w.id = e.away_team_id
               WHERE e.league_key IN ('ucl', 'uel') AND e.status = 'finished' AND e.home_score IS NOT NULL""",
        ).fetchall()
        fake = {"teams": {k: {**v} for k, v in entries.items()}}
        for r in rows:
            keys = []
            for tid, nm in ((r["home_team_id"], r["hn"]), (r["away_team_id"], r["an"])):
                k = cm.team_key(db, tid, nm, fake)
                if k is None:
                    k = f"XX:{nm}"
                    entries.setdefault(k, {"name": nm, "aliases": [], "country": None})
                    fake["teams"][k] = entries[k]
                keys.append(k)
            ko = datetime.fromisoformat(r["kickoff"].replace("Z", "+00:00"))
            cup_rows.append((ko, keys[0], keys[1], r["home_score"], r["away_score"], False))
    for ko, hk, ak, hg, ag, neutral in cup_rows:
        matches.append((ko, cm.GMatch(hk, ak, hg, ag, 0.0, "neutral" if neutral else "cup")))
    return Dataset(matches, entries, cup_rows, skipped)


def fit_at(ds: Dataset, t: datetime, xi: float = cm.XI) -> dict:
    train = [cm.GMatch(g.home, g.away, g.hg, g.ag, (t - ko).total_seconds() / 86400, g.group) for ko, g in ds.matches if ko < t]
    r = cm.fit(train, xi=xi)
    for k, e in r["teams"].items():
        meta = ds.entries.get(k, {})
        e["name"] = meta.get("name") or k.split(":", 1)[1]
        e["aliases"] = meta.get("aliases", [])
        e["country"] = meta.get("country")
    return r


def known(r: dict, key: str) -> bool:
    e = r["teams"].get(key)
    return bool(e) and (e["n_eff"] - e["n_cup"] >= 5 or e["n_cup"] >= 12)
