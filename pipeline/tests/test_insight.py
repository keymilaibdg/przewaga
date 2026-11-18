"""Schedule context (NBA fatigue), price history buckets and the price insight published for the app."""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

import pytest

from app import cli, insight
from app.backtest import prices
from app.backtest.evaluate import Row
from app.cli import Pipeline
from app.db import connect
from app.models.basketball import Game, Ratings
from app.models.schedule import contexts, km, nba_abbr
from tests.fake_api import FakeWorld
from tests.test_pipeline import KEYS, NO_SLEEP, NOW, load

T0 = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)


def test_team_names_and_distance() -> None:
    assert nba_abbr("Cleveland Cavaliers") == "CLE" and nba_abbr("LA Clippers") == "LAC" and nba_abbr("Portland Trail Blazers") == "POR"
    assert nba_abbr("Philadelphia 76ers") == "PHI" and nba_abbr("Unknown FC") is None
    assert 3900 < km((40.751, -73.993), (34.043, -118.267)) < 4000  # New York - Los Angeles


def test_schedule_context_rest_b2b_travel() -> None:
    games = [
        ("g1", T0, "bos", "lal", "Boston Celtics"),
        ("g2", T0 + timedelta(days=1), "nyk", "lal", "New York Knicks"),  # LAL: back-to-back, Boston -> New York
        ("g3", T0 + timedelta(days=4), "lal", "bos", "Los Angeles Lakers"),  # LAL home after 2 nights off; BOS travels
    ]
    c = contexts(games)
    assert c["g1"].away.rest_days == 3 and not c["g1"].away.b2b  # season opener
    assert c["g2"].away.b2b and c["g2"].away.rest_days == 0
    assert 250 < c["g2"].away.travel_km < 320
    assert c["g3"].home.rest_days == 2 and not c["g3"].home.b2b
    assert c["g3"].away.travel_km > 4000 and c["g3"].away.games_last_7d == 1
    assert c["g2"].features()[2] == 1.0  # away back-to-back flag


def test_fatigue_coefficient_is_recovered() -> None:
    """Synthetic league where a back-to-back costs the away team 4 points."""
    rng = random.Random(5)
    teams = [f"t{i}" for i in range(12)]
    names = ["Boston Celtics", "Miami Heat", "Denver Nuggets", "Utah Jazz", "Phoenix Suns", "Dallas Mavericks", "Chicago Bulls", "Detroit Pistons",
             "Orlando Magic", "Atlanta Hawks", "Toronto Raptors", "Sacramento Kings"]
    strength = {t: rng.gauss(0, 4) for t in teams}
    sched = []
    for d in range(160):
        rng.shuffle(teams)
        for i in range(0, 8, 2):
            sched.append((f"{d}:{i}", T0 + timedelta(days=d * (1 if d % 3 else 2)), teams[i], teams[i + 1], names[int(teams[i][1:])]))
    ctx = contexts(sched)
    games = []
    end = sched[-1][1]
    for key, ko, h, a, _ in sched:
        c = ctx[key]
        margin = 2.5 + strength[h] - strength[a] + 4.0 * c.away.b2b - 4.0 * c.home.b2b + rng.gauss(0, 10)
        tot = 220 + rng.gauss(0, 15)
        games.append(Game(h, a, int(round((tot + margin) / 2)), int(round((tot - margin) / 2)), (end - ko).days, c))
    m = Ratings.fit(games, xi=0.0, fatigue=True)
    assert m.fatigue["b2b_away"] == pytest.approx(4.0, abs=2.0)
    assert m.fatigue["b2b_home"] == pytest.approx(-4.0, abs=2.0)
    plain = Ratings.fit(games, xi=0.0)
    assert plain.fatigue == {} and plain.schedule_effect(ctx[sched[-1][0]]) == (0.0, 0.0)


def _row(i: int, price_h: float, outcome: int) -> Row:
    t = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
    ref = (price_h, 4.5, 8.0)
    return Row("epl", "football", f"e{i}", "A – B", t, "2023", "h2h", None, ("home", "draw", "away"), ("1", "X", "2"), (0.6, 0.25, 0.15), ref, ref, ref, None, None, outcome, 20, True, "1:0")


def test_price_buckets_win_rate_and_returns() -> None:
    rows = [_row(i, 1.30, 0 if i % 4 else 2) for i in range(400)]  # favourite at 1.30 wins 75%
    (b,) = [x for x in prices.price_buckets(rows) if x["from"] == 1.25]
    assert b["n"] == 400 and b["winRate"] == pytest.approx(0.75)
    assert b["implied"] == pytest.approx(1 / 1.30, abs=1e-4)
    assert b["roiAvg"] == pytest.approx(0.75 * 1.30 - 1, abs=1e-4)
    assert b["roiTaxed"] == pytest.approx(0.75 * 1.30 * 0.88 - 1, abs=1e-4)
    assert b["winRateLow"] < 0.75 < b["winRateHigh"]


def test_loss_probability_after_series() -> None:
    # a fair 1.30 favourite (p = 1/1.3): after tax every bet loses ~12% on average -> mostly in the red after 50 bets
    p = 1 / 1.30
    assert insight._binom_loss_prob(50, p, 1.30) > 0.7
    assert insight._binom_loss_prob(10, 0.99, 1.30) < 0.1


def test_pipeline_publishes_price_insight(tmp_path, monkeypatch) -> None:
    bfile = tmp_path / "buckets.json"
    bfile.write_text(json.dumps({"leagues": {"epl": {"matches": 999, "source": "test", "buckets": [
        {"from": 1.01, "to": 51.0, "n": 500, "wins": 250, "winRate": 0.5, "winRateLow": 0.45, "winRateHigh": 0.55, "avgPrice": 2.0, "implied": 0.5, "fair": 0.48,
         "roiAvg": -0.05, "roiBest": -0.02, "roiTaxed": -0.15}]}}}))
    monkeypatch.setattr(insight, "PRICE_BUCKETS_PATH", bfile)
    monkeypatch.setattr(cli, "PUBLISH_DIR", tmp_path / "data")
    conn = connect(tmp_path / "db.sqlite3")
    Pipeline(conn, FakeWorld(now=NOW), KEYS, clock=lambda: NOW, sleep=NO_SLEEP).run("morning")
    events = load(tmp_path / "data", "events.json")
    with_odds = [e for e in events if any(m["selections"] for m in e["markets"] if m["market"] in ("1X2", "MONEYLINE"))]
    assert with_odds and all(e["priceInsight"] for e in with_odds)
    for e in with_odds:
        pi = e["priceInsight"]
        ids = {s["id"] for m in e["markets"] for s in m["selections"]}
        assert pi["favouriteSelectionId"] in ids
        fav = next(s for s in pi["selections"] if s["selectionId"] == pi["favouriteSelectionId"])
        assert fav["price"] == min(s["price"] for s in pi["selections"])
        for s in pi["selections"]:
            assert s["selectionId"] in ids
            assert s["breakEvenTaxed"] == pytest.approx(1 / (s["price"] * 0.88), abs=1e-3)
            assert s["evTaxed"] < s["ev"] and s["verdict"]["points"] and s["verdict"]["level"] in ("value", "neutral", "avoid")
            assert 0 <= s["series"]["n10InLoss"] <= 1
        if e["league"]["id"] in ("epl", "nba"):
            assert {f["key"] for f in pi["factors"]} & {"form", "strength", "venue"}
        if e["league"]["id"] == "epl":
            assert any(s["history"] and s["history"]["n"] == 500 for s in pi["selections"])
        if e["league"]["id"] == "nba":
            assert any(f["key"] == "fatigue" for f in pi["factors"])
