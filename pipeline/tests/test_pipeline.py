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
KEYS = {"apisports": "test-key", "odds": "test-odds"}

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
    pipe = Pipeline(conn, world, KEYS, clock=lambda: clock["now"])
    return conn, world, pipe, out, clock


def load(out: Path, name: str):
    return json.loads((out / name).read_text(encoding="utf-8"))


def test_morning_run_end_to_end(env):
    conn, world, pipe, out, _ = env
    summary = pipe.run("morning")

    # data stored for both sports, previous season fetched once for model training
    n = {r["league_key"]: r["n"] for r in conn.execute("SELECT league_key, COUNT(*) n FROM events GROUP BY league_key")}
    assert n["epl"] == 180 and n["nba"] == 320
    # odds names differ between providers ("Tottenham Hotspur" vs "Tottenham") and still match
    assert summary["odds_matched"]["epl"] >= 3 and summary["odds_matched"]["nba"] >= 1
    # unknown leagues in the fake are reported, not fatal
    assert any("ligue" in e or "liga" in e for e in summary["errors"])

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
    meta = load(out, "meta.json")
    assert meta["origin"] == "live" and meta["bookmakers"].get("pinnacle") == "Pinnacle"
    assert {p["id"]: p["status"] for p in meta["providers"]}["the-odds-api"] == "connected"


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
    pipe = Pipeline(conn, FakeWorld(now=NOW), {"apisports": None, "odds": None}, clock=lambda: NOW)
    s = pipe.run("morning")
    assert s["events"] == 0
    meta = load(out, "meta.json")
    assert all(p["status"] in ("not_configured", "unverified") for p in meta["providers"])


def test_invalid_key_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "PUBLISH_DIR", tmp_path / "data")
    conn = connect(tmp_path / "db.sqlite3")
    pipe = Pipeline(conn, FakeWorld(now=NOW), {"apisports": "wrong", "odds": "wrong"}, clock=lambda: NOW)
    s = pipe.run("morning")
    assert any("Missing application key" in e or "token" in e for e in s["errors"])
    meta = load(tmp_path / "data", "meta.json")
    assert {p["id"]: p["status"] for p in meta["providers"]}["api-football"] == "error"
