"""One team identity across sources.

Every source spells teams its own way ('Man United', 'Manchester United FC', 'Manchester United').
The model is fitted on team ids, so history from the CSV files and fixtures from football-data.org must land
on the same id. `resolve` maps (league, source, name) to a team id and remembers the mapping in `team_aliases`.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata

from .matching import similarity
from .providers.common import TeamRef

MIN_SIMILARITY = 0.85


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def display_name(name: str) -> str:
    """'Manchester United FC' -> 'Manchester United', 'AFC Bournemouth' -> 'Bournemouth'."""
    words = name.split()
    while len(words) > 1 and words[-1] in {"FC", "AFC", "CF", "SC"}:
        words.pop()
    while len(words) > 1 and words[0] in {"FC", "AFC"}:
        words.pop(0)
    return " ".join(words)


def resolve(conn: sqlite3.Connection, league_key: str, source: str, ref: TeamRef, create: bool = True) -> str | None:
    """Team id for `ref` in `league_key`. Order: known alias -> native id -> unique similar name -> new team."""
    from .ingest import short_name  # local import: ingest imports this module

    row = conn.execute("SELECT team_id FROM team_aliases WHERE league_key = ? AND source = ? AND name = ?", (league_key, source, ref.name)).fetchone()
    if row:
        if ref.logo:
            conn.execute("UPDATE teams SET logo_url = ? WHERE id = ? AND logo_url IS NULL", (ref.logo, row["team_id"]))
        return row["team_id"]

    tid: str | None = None
    if ref.id and conn.execute("SELECT 1 FROM teams WHERE id = ?", (ref.id,)).fetchone():
        tid = ref.id
    else:
        tid = _similar(conn, league_key, source, ref.name)
    if tid is None:
        if not create:
            return None
        tid = ref.id or f"{source}:{league_key}:{slug(ref.name)}"
        conn.execute(
            "INSERT INTO teams(id, name, short_name, logo_url) VALUES (?,?,?,?) ON CONFLICT(id) DO NOTHING",
            (tid, display_name(ref.name), ref.short or short_name(display_name(ref.name)), ref.logo),
        )
    elif ref.logo:
        conn.execute("UPDATE teams SET logo_url = ? WHERE id = ? AND logo_url IS NULL", (ref.logo, tid))
    conn.execute("INSERT OR IGNORE INTO team_aliases(league_key, source, name, team_id) VALUES (?,?,?,?)", (league_key, source, ref.name, tid))
    return tid


def _similar(conn: sqlite3.Connection, league_key: str, source: str, name: str) -> str | None:
    """Unique best match among teams already known in this league.

    A team that already has a *different* name from the same source is excluded: one source never uses two
    names for one team, so 'Lech' must not be merged into 'Lechia' just because both come from the CSV.
    """
    rows = conn.execute("SELECT team_id, source, name FROM team_aliases WHERE league_key = ?", (league_key,)).fetchall()
    taken = {r["team_id"] for r in rows if r["source"] == source}
    scores: dict[str, float] = {}
    for r in rows:
        if r["team_id"] in taken:
            continue
        scores[r["team_id"]] = max(scores.get(r["team_id"], 0.0), similarity(name, r["name"]))
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] < MIN_SIMILARITY:
        return None
    if len(ranked) > 1 and ranked[1][1] >= ranked[0][1]:
        return None  # ambiguous: better a separate team than a wrong merge
    return ranked[0][0]
