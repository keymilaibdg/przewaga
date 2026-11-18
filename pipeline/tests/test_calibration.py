"""Live use of the ETAP 5 outputs: per-league parameters gate recommendations; cup ratings feed the cup leagues."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app import cli, params
from app.cli import Pipeline
from app.db import connect
from app.engine.evaluate import Context, Market, Quote, Selection, price_market
from app.models import cups as cm
from app.params import LeagueParams, MarketParams
from tests.fake_api import FakeWorld
from tests.test_pipeline import KEYS, NO_SLEEP, NOW, load

T = datetime(2026, 11, 17, 7, 0, tzinfo=timezone.utc)


def _market(model_home: float) -> Market:
    q = lambda p: [Quote("pinnacle", p, T), Quote("best", p * 1.03, T)]  # noqa: E731
    return Market("h2h", "1X2", None, [Selection("home", "1", None, q(2.0), model_home), Selection("draw", "X", None, q(3.6), 0.22), Selection("away", "2", None, q(4.2), 0.18)])


def test_gate_respects_market_status_and_weight() -> None:
    ctx = lambda p: Context(now=T, kickoff=T + timedelta(hours=10), completeness=0.8, both_teams_known=True, params=p)  # noqa: E731
    ok = LeagueParams("epl", markets={"h2h": MarketParams(0.5, 1.0, "validated")})
    assert price_market(_market(0.60), lambda p: 0.02, ctx(ok))
    waiting = LeagueParams("epl", status="validating", markets={"h2h": MarketParams(0.5, 1.0, "validating", "test")})
    mk = _market(0.60)
    assert price_market(mk, lambda p: 0.02, ctx(waiting)) == []
    assert "walidacji" in mk.verdict
    # weight 0: the final probability is the market -> no edge left
    zero = LeagueParams("epl", markets={"h2h": MarketParams(0.0, 1.0, "validated")})
    mk = _market(0.60)
    assert price_market(mk, lambda p: 0.02, ctx(zero)) == []
    assert mk.selections[0].model_prob == pytest.approx(mk.selections[0].fair_prob)
    # a higher EV threshold removes the tip
    strict = LeagueParams("epl", min_ev=0.30, markets={"h2h": MarketParams(0.5, 1.0, "validated")})
    assert price_market(_market(0.60), lambda p: 0.02, ctx(strict)) == []


def test_params_load(tmp_path) -> None:
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"generated_at": "2026-11-18T10:00:00Z", "leagues": {
        "epl": {"min_ev": 0.04, "xi": 0.001, "markets": {"h2h": {"model_weight": 0.3, "hw_scale": 1.4, "status": "validated"}, "totals": {"model_weight": 0.0, "status": "validating"}}},
        "ucl": {"status": "validating", "markets": {"h2h": {"model_weight": 0.5, "status": "validating"}}},
    }}))
    p = params.load(f)
    assert p["epl"].status == "validated" and p["epl"].min_ev == 0.04 and p["epl"].xi == 0.001
    assert p["epl"].can_recommend("h2h") and not p["epl"].can_recommend("totals")
    assert p["ucl"].has_model and not p["ucl"].can_recommend("h2h")
    assert p["euroleague"].status == "market_only" and p["nba"].status == "validated"  # not in file: ETAP 4 defaults
    assert params.load(tmp_path / "missing.json")["laliga"].weight("h2h") == 0.5


def test_pipeline_with_calibration_file(tmp_path, monkeypatch) -> None:
    """NBA in validation -> model shown, no NBA tips, flag in the event; meta lists the model status."""
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"generated_at": "x", "leagues": {"nba": {"markets": {m: {"model_weight": 0.2, "status": "validating", "reason": "test"} for m in ("h2h", "spreads", "totals")}}}}))
    monkeypatch.setenv("PRZEWAGA_CALIBRATION", str(f))
    out = tmp_path / "data"
    monkeypatch.setattr(cli, "PUBLISH_DIR", out)
    conn = connect(tmp_path / "db.sqlite3")
    pipe = Pipeline(conn, FakeWorld(now=NOW), KEYS, clock=lambda: NOW, sleep=NO_SLEEP)
    pipe.run("morning")
    assert conn.execute("SELECT COUNT(*) FROM recommendations r JOIN events e ON e.id = r.event_id WHERE e.league_key = 'nba'").fetchone()[0] == 0
    events = load(out, "events.json")
    nba = [e for e in events if e["league"]["id"] == "nba" and e["markets"]]
    assert nba and all(any("walidacji" in fl for fl in e["flags"]) for e in nba)
    meta = load(out, "meta.json")
    st = {m["league"]: m for m in meta["models"]}
    assert st["nba"]["status"] == "validating" and st["epl"]["status"] == "validated" and st["euroleague"]["status"] == "market_only"


def test_cup_model_maps_database_teams(tmp_path) -> None:
    conn = connect(tmp_path / "db.sqlite3")
    for tid, name in (("fdo:5", "FC Bayern München"), ("fdo:498", "Sporting Clube de Portugal"), ("fdo:999", "Unknown FC")):
        conn.execute("INSERT INTO teams(id, name) VALUES (?, ?)", (tid, name))
    conn.execute("INSERT INTO team_aliases VALUES ('bundesliga', 'csv', 'Bayern Munich', 'fdo:5')")
    for i, (h, a) in enumerate((("fdo:5", "fdo:498"), ("fdo:498", "fdo:999"))):
        conn.execute("INSERT INTO events(id, sport, league_key, season, home_team_id, away_team_id, kickoff, status, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (f"e{i}", "football", "ucl", "2026", h, a, "2026-11-25T20:00:00Z", "scheduled", "2026-11-18T00:00:00Z"))
    ratings = {"base": 0.1, "rho": -0.05, "cup_home": 0.2, "teams": {
        "GER:Bayern Munich": {"att": 0.6, "dfn": -0.5, "n_eff": 60, "n_cup": 8, "name": "Bayern Munich", "aliases": []},
        "POR:Sp Lisbon": {"att": 0.3, "dfn": -0.3, "n_eff": 50, "n_cup": 6, "name": "Sp Lisbon", "aliases": ["Sporting CP"]},
    }}
    m = cm.cup_model(conn, "ucl", T, ratings)
    assert m is not None and set(m.teams) == {"fdo:5", "fdo:498"}
    assert m.known("fdo:5") and m.known("fdo:498") and not m.known("fdo:999")
    lam, mu = m.rates("fdo:5", "fdo:498")
    assert lam == pytest.approx(np.exp(0.1 + 0.6 - 0.3 + 0.2)) and mu == pytest.approx(np.exp(0.1 + 0.3 - 0.5))


def test_cup_fit_links_leagues_through_cup_games() -> None:
    """League B is weaker than A: visible only through A-vs-B cup games."""
    rng = np.random.default_rng(0)
    ms = []
    strength = {f"A{i}": 0.3 + rng.normal(0, 0.1) for i in range(6)} | {f"B{i}": -0.3 + rng.normal(0, 0.1) for i in range(6)}
    teams = list(strength)
    for k in range(1500):
        lg = "A" if k % 2 else "B"
        pool = [t for t in teams if t.startswith(lg)] if k % 5 else teams
        h, a = rng.choice(pool, 2, replace=False)
        grp = lg if k % 5 else "cup"
        lam, mu = np.exp(0.3 + strength[h] - strength[a]), np.exp(0.05 + strength[a] - strength[h])
        ms.append(cm.GMatch(h, a, int(rng.poisson(lam)), int(rng.poisson(mu)), k * 0.3, grp))
    r = cm.fit(ms)
    a_att = np.mean([r["teams"][t]["att"] - r["teams"][t]["dfn"] for t in teams if t.startswith("A")])
    b_att = np.mean([r["teams"][t]["att"] - r["teams"][t]["dfn"] for t in teams if t.startswith("B")])
    assert a_att - b_att > 0.6
