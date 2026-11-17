"""SQLite storage. Odds snapshots and recommendations are append-only / never deleted."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
PRAGMA journal_mode = DELETE;  -- single-file DB: safe to commit to git after each run
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS leagues (
    key TEXT PRIMARY KEY,
    provider_id INTEGER,
    season TEXT,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,              -- 'fdo:64' (football-data.org) / 'bdl:2' (balldontlie) / '<source>:<league>:<slug>'
    name TEXT NOT NULL,
    short_name TEXT,
    logo_url TEXT
);

-- Name used by a source for a team in a league -> canonical team id (see app/teams.py).
CREATE TABLE IF NOT EXISTS team_aliases (
    league_key TEXT NOT NULL,
    source TEXT NOT NULL,             -- fdo | csv | bdl | odds
    name TEXT NOT NULL,
    team_id TEXT NOT NULL REFERENCES teams(id),
    PRIMARY KEY (league_key, source, name)
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,              -- 'fb:fdo:<match>' / 'fb:csv:<league>:<date>:<home>:<away>' / 'bb:bdl:<game>' / 'odds:<event>'
    sport TEXT NOT NULL,
    league_key TEXT NOT NULL,
    season TEXT NOT NULL,
    home_team_id TEXT NOT NULL REFERENCES teams(id),
    away_team_id TEXT NOT NULL REFERENCES teams(id),
    kickoff TEXT NOT NULL,            -- ISO UTC
    status TEXT NOT NULL,             -- scheduled | live | finished | postponed | cancelled
    home_score INTEGER,
    away_score INTEGER,
    venue TEXT,
    odds_event_id TEXT,               -- The Odds API event id once matched
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_kickoff ON events(kickoff);
CREATE INDEX IF NOT EXISTS ix_events_league ON events(league_key, season);

CREATE TABLE IF NOT EXISTS odds_snapshots (
    id INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id),
    bookmaker TEXT NOT NULL,
    market TEXT NOT NULL,             -- h2h | totals | spreads
    selection TEXT NOT NULL,          -- home | draw | away | over | under
    line REAL,
    price REAL NOT NULL,
    source_updated_at TEXT,
    captured_at TEXT NOT NULL,
    UNIQUE(event_id, bookmaker, market, selection, line, source_updated_at)
);
CREATE INDEX IF NOT EXISTS ix_odds_event ON odds_snapshots(event_id, captured_at);

CREATE TABLE IF NOT EXISTS injuries (
    id INTEGER PRIMARY KEY,
    league_key TEXT NOT NULL,
    team_id TEXT NOT NULL,
    player TEXT NOT NULL,
    kind TEXT,                        -- 'Missing Fixture' | 'Questionable'
    reason TEXT,
    fixture_event_id TEXT,
    fetched_at TEXT NOT NULL,
    UNIQUE(team_id, player, fixture_event_id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,              -- '<event_id>:<market>:<selection>:<line>'
    event_id TEXT NOT NULL REFERENCES events(id),
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    line REAL,
    label TEXT NOT NULL,
    bookmaker TEXT NOT NULL,
    price REAL NOT NULL,              -- price at publication (never changed)
    current_price REAL,
    model_prob REAL NOT NULL,
    prob_low REAL NOT NULL,
    prob_high REAL NOT NULL,
    implied_prob REAL NOT NULL,
    fair_prob REAL NOT NULL,
    ev REAL NOT NULL,
    quality INTEGER NOT NULL,
    risk TEXT NOT NULL,
    reasons_for TEXT NOT NULL,        -- JSON list
    reasons_against TEXT NOT NULL,    -- JSON list
    model_version TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,             -- active | withdrawn | settled
    withdraw_reason TEXT,
    closing_price REAL,
    result TEXT,                      -- won | lost | void | pending
    profit REAL,
    settled_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_recs_event ON recommendations(event_id);

CREATE TABLE IF NOT EXISTS provider_calls (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL,           -- football-data-org | football-data-csv | balldontlie | the-odds-api
    endpoint TEXT NOT NULL,
    params TEXT,
    http_status INTEGER,
    ok INTEGER NOT NULL,
    error TEXT,
    remaining INTEGER,                -- provider-reported remaining quota, if any
    cost INTEGER NOT NULL DEFAULT 1,
    called_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_calls_provider ON provider_calls(provider, called_at);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    ok INTEGER,
    summary TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def upsert(conn: sqlite3.Connection, table: str, row: dict[str, Any], key: str = "id") -> None:
    cols = list(row)
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c != key)
    conn.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) ON CONFLICT({key}) DO UPDATE SET {updates}",
        [row[c] for c in cols],
    )


def dumps(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)
