"""End-to-end: run the pipeline against the offline fake providers and validate stored data and published JSON."""
import json
from datetime import timedelta, timezone, datetime
from pathlib import Path

import pytest

from app import cli, config
from app.cli import Pipeline
from app.db import connect
from tests.fake_api import FakeWorld

NOW = datetime(2026, 11, 17, 7, 0, tzinfo=timezone.utc)
KEYS = {"fdo": "test-fdo", "bdl": "test-bdl", "odds": "test-odds"}
NO_SLEEP = lambda s: None  # noqa: E731

# Required keys per domain.ts interface (subset that the UI dereferences).
EVENT_KEYS = {"id", "origin", "sport", "league", "home", "away", "kickoff", "status", "venue", "markets", "recommendations", "noBetReason", "formHome", "formAway", "stats", "absences", "lineups", "h2h", "sources", "lastUpdated", "flags"}
REC_KEYS = {"id", "eventId", "selectionId", "market", "label", "bookmaker", "price", "modelProb", "probLow", "probHigh", "impliedProb", "fairProb", "ev", "quality", "risk", "reasonsFor", "reasonsAgainst", "generatedAt", "updatedAt", "status"}
HIST_KEYS = {"id", "origin", "sport", "eventLabel", "league", "kickoff", "market", "label", "bookmaker", "openingPrice", "closingPrice", "modelProb", "ev", "quality", "risk", "generatedAt", "result", "finalScore", "profit"}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    out = tmp_path / "data"
    monkeypatch.setattr(cli, "PUBLISH_DIR", out)
    conn = connect(tmp_path / "db.sqlite3")
    world = FakeWorld(now=NOW)
    clock = {"now": NOW}
    pipe = Pipeline(conn, world, KEYS, clock=lambda: clock["now"], sleep=NO_SLEEP)
    return conn, world, pipe, out, clock


def load(out: Path, name: str):
    return json.loads((out / name).read_text(encoding="utf-8"))


def test_morning_run_end_to_end(env):
    conn, world, pipe, out, _ = env
    summary = pipe.run("morning")

    # football: current season from football-data.org + previous season from the CSV (once), current-season CSV rows merged
    n = {r["league_key"]: r["n"] for r in conn.execute("SELECT league_key, COUNT(*) n FROM events GROUP BY league_key")}
    assert n["epl"] == 180 and n["nba"] == 320 and n["uel"] == 2
    # one team identity across three spellings ('Man United' / 'Manchester United FC' / 'Manchester United')
    epl_teams = conn.execute("SELECT COUNT(DISTINCT t) n FROM (SELECT home_team_id t FROM events WHERE league_key='epl' UNION SELECT away_team_id FROM events WHERE league_key='epl')").fetchone()["n"]
    assert epl_teams == 10
    assert summary["fixtures"]["football-data.org"] == 90 and summary["csv_history"] == 140 and summary["fixtures"]["the-odds-api"] == 2
    # odds names differ between providers ("Tottenham Hotspur" vs "Tottenham") and still match
    assert summary["odds_matched"]["epl"] >= 3 and summary["odds_matched"]["nba"] >= 1 and summary["odds_matched"]["uel"] == 2
    # missing CSV files are reported, not fatal; no unmatched odds in fixture-API leagues
    assert any("historia laliga" in e for e in summary["errors"])
    assert not any("bez pary" in e for e in summary["errors"])
    # balldontlie: 2 seasons x 2 pages
    assert sum(1 for c in world.calls if "balldontlie" in c) == 4

    events = load(out, "events.json")
    assert events and all(EVENT_KEYS <= set(e) for e in events)
    for e in events:
        active = [r for r in e["recommendations"] if r["status"] == "active"]
        assert (e["noBetReason"] is None) == bool(active)
        for r in e["recommendations"]:
            assert REC_KEYS <= set(r)
            assert r["ev"] >= config.MIN_EV and r["quality"] >= config.MIN_QUALITY and r["price"] <= config.MAX_PRICE
            assert r["probLow"] <= r["modelProb"] <= r["probHigh"]
            assert r["reasonsFor"] and len(r["reasonsAgainst"]) >= 1
        for m in e["markets"]:
            for s in m["selections"]:
                assert s["quotes"] and all(q["price"] > 1 for q in s["quotes"])
        # never invent data: xG and lineups are explicitly missing
        assert e["lineups"]["status"] == "unavailable"
        if e["sport"] == "football":
            assert next(s for s in e["stats"] if s["key"] == "xg")["home"] is None
    # Europa League: odds shown, priced by the market, never recommended
    uel = [e for e in events if e["league"]["id"] == "uel"]
    assert len(uel) == 2 and all(not e["recommendations"] and any("tylko kursy" in f for f in e["flags"]) for e in uel)
    assert all(m["verdict"].startswith("Brak modelu") for e in uel for m in e["markets"] if m.get("available", True))
    assert next(s for s in uel[0]["sources"] if s["kind"] == "fixtures")["provider"] == "The Odds API"
    epl = next(e for e in events if e["league"]["id"] == "epl")
    assert next(s for s in epl["sources"] if s["kind"] == "fixtures")["provider"] == "football-data.org"
    meta = load(out, "meta.json")
    assert meta["origin"] == "live" and meta["bookmakers"].get("pinnacle") == "Pinnacle"
    status = {p["id"]: p["status"] for p in meta["providers"]}
    assert status == {"football-data-org": "connected", "football-data-csv": "connected", "balldontlie": "connected", "the-odds-api": "connected", "pl-books": "unverified",
                      "clubelo": "connected", "nba-injury-report": "error"}  # the fake world serves no injury PDF by default


def test_recommendations_lifecycle_settlement_and_history(env):
    conn, world, pipe, out, clock = env
    pipe.run("morning")
    before = conn.execute("SELECT COUNT(*) n FROM recommendations WHERE status = 'active'").fetchone()["n"]
    assert before >= 1, "the fake market is skewed, the engine should find at least one value bet"

    # Market becomes efficient (no skew): re-run => stale reasons are withdrawn, nothing deleted.
    world.odds_skew = 0.0
    clock["now"] = world.now = NOW + timedelta(hours=8)
    pipe.errors.clear()
    pipe.run("afternoon")
    total_after = conn.execute("SELECT COUNT(*) n FROM recommendations").fetchone()["n"]
    assert total_after >= before
    withdrawn = conn.execute("SELECT * FROM recommendations WHERE status = 'withdrawn'").fetchall()
    for w in withdrawn:
        assert w["withdraw_reason"]

    # Four days later all matches are played: active recommendations get settled with profit and CLV.
    clock["now"] = world.now = NOW + timedelta(days=4)
    pipe.errors.clear()
    pipe.run("morning")
    settled = conn.execute("SELECT * FROM recommendations WHERE status = 'settled'").fetchall()
    assert settled, "finished events must be settled"
    for s in settled:
        assert s["result"] in ("won", "lost", "void")
        assert s["profit"] == pytest.approx(s["price"] - 1 if s["result"] == "won" else (-1 if s["result"] == "lost" else 0))
    hist = load(out, "history.json")
    assert all(HIST_KEYS <= set(h) for h in hist)
    assert {h["result"] for h in hist} <= {"won", "lost", "void", "pending", "withdrawn"}
    assert len(hist) == conn.execute("SELECT COUNT(*) n FROM recommendations").fetchone()["n"]
    # Europa League results came from /scores (no tips there, but the games are older than 40 h)
    assert {r["status"] for r in conn.execute("SELECT status FROM events WHERE league_key = 'uel'")} == {"finished"}


def test_odds_budget_skips_leagues_instead_of_overspending(env, monkeypatch):
    conn, world, pipe, out, _ = env
    monkeypatch.setattr(cli, "ODDS_MONTHLY_CREDITS", 0)
    from app.providers.http import odds_budget

    pipe.odds.c.budget = odds_budget(conn, 3, lambda: NOW)  # ~0 credits/day
    s = pipe.run("morning")
    assert not s["odds_matched"]
    assert any("pominięto" in e for e in s["errors"])
    assert conn.execute("SELECT COALESCE(SUM(cost),0) c FROM provider_calls WHERE provider='the-odds-api' AND http_status IS NOT NULL").fetchone()["c"] == 0


def test_missing_keys_still_publishes(tmp_path, monkeypatch):
    out = tmp_path / "data"
    monkeypatch.setattr(cli, "PUBLISH_DIR", out)
    conn = connect(tmp_path / "db.sqlite3")
    pipe = Pipeline(conn, FakeWorld(now=NOW), {"fdo": None, "bdl": None, "odds": None}, clock=lambda: NOW, sleep=NO_SLEEP)
    s = pipe.run("morning")
    assert s["events"] == 0, "the CSV (no key needed) brings history only"
    meta = load(out, "meta.json")
    status = {p["id"]: p["status"] for p in meta["providers"]}
    assert status.pop("football-data-csv") == "connected" and status.pop("clubelo") == "connected"  # no key needed
    assert all(v in ("not_configured", "unverified") for v in status.values())


def test_invalid_key_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "PUBLISH_DIR", tmp_path / "data")
    conn = connect(tmp_path / "db.sqlite3")
    pipe = Pipeline(conn, FakeWorld(now=NOW), {"fdo": "wrong", "bdl": "wrong", "odds": "wrong"}, clock=lambda: NOW, sleep=NO_SLEEP)
    s = pipe.run("morning")
    assert any("terminarz epl" in e and "403" in e for e in s["errors"])
    meta = load(tmp_path / "data", "meta.json")
    status = {p["id"]: p["status"] for p in meta["providers"]}
    assert status["football-data-org"] == status["balldontlie"] == status["the-odds-api"] == "error"
