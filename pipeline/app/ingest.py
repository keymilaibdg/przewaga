"""Write normalised provider data into SQLite. Idempotent; odds are append-only."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from .config import LeagueConfig
from .db import upsert
from . import teams
from .matching import best_match
from .providers.common import Fixture, Injury
from .providers.http import iso
from .providers.odds_api import OddsEvent


# Same pair of team ids within this window = the same match reported by two sources (CSV has no exact time).
SAME_EVENT_WINDOW = timedelta(hours=36)
# Sources whose kickoff time is exact; CSV and odds-only events yield to them.
PRECISE_SOURCES = {"fdo", "bdl"}


def store_fixtures(conn: sqlite3.Connection, fixtures: list[Fixture], now: datetime, source: str) -> int:
    """Upsert fixtures/results. Team names go through the resolver; duplicates from other sources are merged."""
    n = 0
    for f in fixtures:
        hid = teams.resolve(conn, f.league_key, source, f.home)
        aid = teams.resolve(conn, f.league_key, source, f.away)
        if not hid or not aid or hid == aid:
            continue
        new = {
            "id": f.id,
            "sport": f.sport,
            "league_key": f.league_key,
            "season": f.season,
            "home_team_id": hid,
            "away_team_id": aid,
            "kickoff": iso(f.kickoff),
            "status": f.status,
            "home_score": f.home_score,
            "away_score": f.away_score,
            "venue": f.venue,
            "updated_at": iso(now),
        }
        row = conn.execute("SELECT * FROM events WHERE id = ?", (f.id,)).fetchone() or find_same_event(conn, f.league_key, hid, aid, f.kickoff, f.id)
        if row is None:
            upsert(conn, "events", new)
        else:
            merge_event(conn, row, new, precise=source in PRECISE_SOURCES)
        n += 1
    conn.commit()
    return n


def find_same_event(conn: sqlite3.Connection, league_key: str, home_id: str, away_id: str, kickoff: datetime, new_id: str) -> sqlite3.Row | None:
    """The same match already stored by *another* source. Within one source ids are authoritative:
    NBA plays two games between the same teams on consecutive nights."""
    prefix = source_prefix(new_id)
    return conn.execute(
        """SELECT * FROM events WHERE league_key = ? AND home_team_id = ? AND away_team_id = ? AND kickoff BETWEEN ? AND ?
           AND substr(id, 1, ?) != ? ORDER BY ABS(julianday(kickoff) - julianday(?)) LIMIT 1""",
        (league_key, home_id, away_id, iso(kickoff - SAME_EVENT_WINDOW), iso(kickoff + SAME_EVENT_WINDOW), len(prefix), prefix, iso(kickoff)),
    ).fetchone()


def source_prefix(event_id: str) -> str:
    """'fb:fdo:123' -> 'fb:fdo:', 'odds:abc' -> 'odds:'."""
    parts = event_id.split(":")
    return ":".join(parts[:2]) + ":" if len(parts) > 2 and parts[0] in ("fb", "bb") else parts[0] + ":"


def merge_event(conn: sqlite3.Connection, row: sqlite3.Row, new: dict, precise: bool) -> None:
    """Update an existing event (keeps its id: odds and recommendations point at it).

    A final result is never downgraded (football-data.org shows results with a delay, CSV may already have them).
    """
    upd: dict = {"updated_at": new["updated_at"]}
    if precise or row["id"] == new["id"]:
        upd.update(kickoff=new["kickoff"], season=new["season"], venue=new["venue"] or row["venue"])
    has_result = row["status"] == "finished" and row["home_score"] is not None
    if new["status"] == "finished" and new["home_score"] is not None:
        upd.update(status="finished", home_score=new["home_score"], away_score=new["away_score"])
    elif not has_result:
        upd.update(status=new["status"], home_score=new["home_score"], away_score=new["away_score"])
    sets = ", ".join(f"{k} = ?" for k in upd)
    conn.execute(f"UPDATE events SET {sets} WHERE id = ?", (*upd.values(), row["id"]))


def store_injuries(conn: sqlite3.Connection, lg: LeagueConfig, items: list[Injury], now: datetime) -> int:
    for i in items:
        conn.execute(
            """INSERT INTO injuries(league_key, team_id, player, kind, reason, fixture_event_id, fetched_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(team_id, player, fixture_event_id) DO UPDATE SET kind=excluded.kind, reason=excluded.reason, fetched_at=excluded.fetched_at""",
            (lg.key, i.team_id, i.player, i.kind, i.reason, i.fixture_id, iso(now)),
        )
    conn.commit()
    return len(items)


def store_odds(conn: sqlite3.Connection, lg: LeagueConfig, events: list[OddsEvent], now: datetime) -> dict[str, int]:
    """Match odds events to fixtures and append snapshots. Returns counters."""
    rows = conn.execute(
        """SELECT e.id, e.kickoff, h.name AS home, a.name AS away FROM events e
           JOIN teams h ON h.id = e.home_team_id JOIN teams a ON a.id = e.away_team_id
           WHERE e.league_key = ? AND e.status = 'scheduled' AND e.kickoff BETWEEN ? AND ?""",
        (lg.key, iso(now - timedelta(hours=6)), iso(now + timedelta(days=10))),
    ).fetchall()
    fixtures = [(r["id"], r["home"], r["away"], datetime.fromisoformat(r["kickoff"].replace("Z", "+00:00"))) for r in rows]

    matched = unmatched = quotes = 0
    for oe in events:
        hit = best_match(oe.home_team, oe.away_team, oe.commence_time, fixtures, get=lambda c: (c[1], c[2], c[3]))
        if hit is None:
            unmatched += 1
            continue
        matched += 1
        event_id = hit[0]
        conn.execute("UPDATE events SET odds_event_id = ? WHERE id = ?", (oe.id, event_id))
        for q in oe.quotes:
            sel = _selection(q.market, q.outcome_name, oe.home_team, oe.away_team)
            if sel is None:
                continue
            cur = conn.execute(
                """INSERT OR IGNORE INTO odds_snapshots(event_id, bookmaker, market, selection, line, price, source_updated_at, captured_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (event_id, q.bookmaker, q.market, sel, q.point, q.price, q.updated_at, iso(now)),
            )
            quotes += cur.rowcount
        _remember_bookmakers(conn, {q.bookmaker: q.bookmaker_title for q in oe.quotes})
    conn.commit()
    return {"matched": matched, "unmatched": unmatched, "quotes": quotes}


def _selection(market: str, name: str, home: str, away: str) -> str | None:
    if market == "totals":
        return {"over": "over", "under": "under"}.get(name.lower())
    if name == home:
        return "home"
    if name == away:
        return "away"
    if market == "h2h" and name.lower() == "draw":
        return "draw"
    return None


def _remember_bookmakers(conn: sqlite3.Connection, titles: dict[str, str]) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS bookmakers (key TEXT PRIMARY KEY, title TEXT NOT NULL)")
    for k, t in titles.items():
        conn.execute("INSERT INTO bookmakers(key, title) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET title = excluded.title", (k, t))


def short_name(name: str) -> str:
    """3-letter code: 'Manchester United' -> MUN, 'Los Angeles Lakers' -> LAL, 'Arsenal' -> ARS."""
    import unicodedata

    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = [w for w in plain.replace(".", " ").replace("-", " ").split() if w.lower() not in {"fc", "cf", "ac", "sc", "afc", "bc", "kk", "1"}]
    if not words:
        return name[:3].upper()
    if len(words) == 1:
        return words[0][:3].upper()
    if len(words) >= 3:
        return "".join(w[0] for w in words[:3]).upper()
    return (words[0][0] + words[1][:2]).upper()
