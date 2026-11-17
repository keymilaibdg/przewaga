"""Unit tests: odds math (mirrors frontend/src/lib/odds.test.ts), models, matching, HTTP client."""
import math
import random
import sqlite3
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.db import connect
from app.engine.evaluate import Context, Market, Quote, Selection, price_market, quality, recommendable
from app.engine.odds import closing_line_value, expected_value, fair_probabilities, implied_probability, kelly_fraction, overround
from app.matching import best_match, normalize, similarity
from app.models.basketball import Game, Ratings
from app.models.football import DixonColes, Match, outcome_probs, total_over
from app.providers.http import ApiClient, BudgetExceeded, HttpResponse, ProviderError, api_sports_budget, odds_budget

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


# ---------- odds math (same cases as the TypeScript suite) ----------

def test_implied_probability():
    assert implied_probability(1.35) == pytest.approx(0.7407407407)
    with pytest.raises(ValueError):
        implied_probability(1.0)


def test_overround_and_fair():
    assert overround([2.1, 3.4, 3.6]) == pytest.approx(0.0480859, abs=1e-6)
    fair = fair_probabilities([2.1, 3.4, 3.6])
    assert sum(fair) == pytest.approx(1)
    assert fair[0] > fair[1] > fair[2]


def test_ev_brief_example_and_edges():
    assert expected_value(0.82, 1.35) == pytest.approx(0.107)
    assert expected_value(0.7, 1.35) < 0
    with pytest.raises(ValueError):
        expected_value(1.2, 2)


def test_kelly_and_clv():
    assert kelly_fraction(0.4, 2.0) == 0
    assert kelly_fraction(0.55, 2.0) == pytest.approx(0.1)
    assert closing_line_value(2.1, 2.0) == pytest.approx(0.05)


# ---------- models ----------

def _sim_league(seed=1, rounds=2):
    rng = np.random.default_rng(seed)
    n = 12
    att = rng.normal(0, 0.3, n)
    att -= att.mean()
    dfn = rng.normal(0, 0.25, n)
    dfn -= dfn.mean()
    ms = []
    for _ in range(rounds):
        for i in range(n):
            for j in range(n):
                if i != j:
                    lam, mu = math.exp(0.15 + att[i] + dfn[j] + 0.25), math.exp(0.15 + att[j] + dfn[i])
                    ms.append(Match(f"t{i}", f"t{j}", int(rng.poisson(lam)), int(rng.poisson(mu)), float(rng.uniform(0, 300))))
    return ms, att


def test_dixon_coles_recovers_strengths_and_is_coherent():
    ms, att = _sim_league()
    m = DixonColes.fit(ms)
    idx = {t: i for i, t in enumerate(m.teams)}
    fitted = np.array([m.att[idx[f"t{i}"]] for i in range(12)])
    assert np.corrcoef(fitted, att)[0, 1] > 0.85
    assert 0.1 < m.home_adv < 0.4
    mat = m.score_matrix("t0", "t1")
    assert mat.sum() == pytest.approx(1)
    o = outcome_probs(mat)
    assert sum(o.values()) == pytest.approx(1)
    assert total_over(mat, 0.5) > total_over(mat, 2.5) > total_over(mat, 4.5)


def test_dixon_coles_unknown_team_and_small_sample():
    ms, _ = _sim_league()
    m = DixonColes.fit(ms)
    assert not m.known("promoted-team")
    assert m.half_width(0.5, "promoted-team", "t1") > m.half_width(0.5, "t0", "t1")
    tiny = DixonColes.fit(ms[:5])
    assert tiny.n_matches == 5 and np.allclose(tiny.att, 0)


def test_basketball_ratings():
    rng = np.random.default_rng(2)
    r = rng.normal(0, 5, 10)
    games = []
    for _ in range(600):
        i, j = rng.choice(10, 2, replace=False)
        mar = 2.5 + r[i] - r[j] + rng.normal(0, 12)
        tot = 225 + rng.normal(0, 17)
        games.append(Game(f"b{i}", f"b{j}", int(round((tot + mar) / 2)), int(round((tot - mar) / 2)), float(rng.uniform(0, 150))))
    b = Ratings.fit(games)
    assert np.corrcoef([b.rating[f"b{i}"] for i in range(10)], r)[0, 1] > 0.9
    assert 9 < b.sigma_m < 15
    assert b.p_home_cover("b0", "b1", -100.5) < 0.01 < 0.99 < b.p_home_cover("b0", "b1", 100.5)
    assert b.p_over("b0", "b1", 150.5) > 0.99


# ---------- engine ----------

def _market(prices_by_book, model_probs, captured=NOW):
    sels = []
    for i, (key, p) in enumerate(zip(("home", "draw", "away"), model_probs)):
        sels.append(Selection(key, key, None, [Quote(b, ps[i], captured) for b, ps in prices_by_book.items()], p))
    return Market("h2h", "1X2", None, sels)


def test_engine_never_recommends_negative_ev():
    mk = _market({"pinnacle": [2.0, 3.5, 4.0]}, [0.40, 0.30, 0.30])
    ctx = Context(NOW, NOW + timedelta(days=1), 0.9, True)
    for c in price_market(mk, lambda p: 0.03, ctx):
        assert c.ev >= 0.02 and c.quality >= 60


def test_engine_finds_value_and_respects_stale_odds():
    mk = _market({"pinnacle": [2.2, 3.5, 3.4], "soft": [2.45, 3.3, 3.1]}, [0.55, 0.25, 0.20])
    ctx = Context(NOW, NOW + timedelta(days=1), 0.95, True)
    cands = price_market(mk, lambda p: 0.02, ctx)
    assert cands and cands[0].sel.key == "home" and cands[0].best.bookmaker == "soft"
    stale = _market({"pinnacle": [2.2, 3.5, 3.4]}, [0.55, 0.25, 0.20], captured=NOW - timedelta(hours=30))
    assert price_market(stale, lambda p: 0.02, ctx) == []


def test_engine_blocks_unknown_teams_long_prices_and_integer_lines():
    ctx_unknown = Context(NOW, NOW + timedelta(days=1), 0.95, both_teams_known=False)
    mk = _market({"pinnacle": [2.2, 3.5, 3.4], "soft": [2.6, 3.3, 3.1]}, [0.55, 0.25, 0.20])
    assert price_market(mk, lambda p: 0.02, ctx_unknown) == []
    long = _market({"pinnacle": [1.3, 5.5, 9.0], "soft": [1.25, 5.0, 11.0]}, [0.6, 0.15, 0.25])
    assert all(c.best.price <= 5 for c in price_market(long, lambda p: 0.02, Context(NOW, NOW + timedelta(days=1), 0.95, True)))
    s = Selection("over", "o", 2.0, [Quote("x", 2.5, NOW)], 0.6)
    from app.engine.evaluate import Candidate

    c = Candidate(Market("totals", "t", 2.0, [s]), s, s.quotes[0], 0.2, 0.4, 80, "low", 0.02)
    assert not recommendable(c, Context(NOW, NOW + timedelta(days=1), 0.95, True))


def test_engine_refuses_when_model_and_market_disagree_wildly():
    # Model says 75%, sharp market says ~45%: likely missing information => no recommendation.
    mk = _market({"pinnacle": [2.15, 3.4, 3.9], "soft": [2.3, 3.3, 3.6]}, [0.75, 0.15, 0.10])
    cands = price_market(mk, lambda p: 0.02, Context(NOW, NOW + timedelta(days=1), 0.95, True))
    assert cands == [] and "różnią się zbyt mocno" in mk.verdict


def test_quality_is_lowered_by_missing_data():
    assert quality(1.0, 1.0, 0.05, False, 2.0, True) > quality(1.0, 0.4, 0.05, False, 2.0, True)
    assert quality(1.0, 1.0, 0.05, False, 2.0, False) < quality(1.0, 1.0, 0.05, False, 2.0, True) - 15


# ---------- matching ----------

def test_name_normalisation_and_similarity():
    assert normalize("Bayern München") == normalize("Bayern Munich")
    assert normalize("Tottenham Hotspur") == normalize("Tottenham")
    assert similarity("Brighton and Hove Albion", "Brighton") > 0.9
    assert similarity("Manchester United", "Manchester City") < 0.72


def test_best_match_time_window_and_swapped_sides():
    class C:
        def __init__(self, h, a, t):
            self.home_team, self.away_team, self.commence_time = h, a, t

    cands = [C("Arsenal", "Chelsea", NOW + timedelta(hours=1)), C("Chelsea", "Arsenal", NOW + timedelta(days=60))]
    assert best_match("Arsenal", "Chelsea", NOW, cands) is cands[0]
    assert best_match("Chelsea", "Arsenal", NOW, cands) is None  # reverse fixture is far away in time
    assert best_match("Arsenal", "Chelsea", NOW + timedelta(hours=12), cands) is None


# ---------- HTTP client ----------

class ScriptedTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, headers):
        self.urls.append(url)
        return self.responses.pop(0)


def _client(conn, transport, budget=lambda: 50, provider="api-football"):
    return ApiClient(provider, "https://x.test", {"x-apisports-key": "secret"}, conn, transport, budget, sleep=lambda s: None, clock=lambda: NOW)


def test_http_retries_429_then_succeeds(tmp_path):
    conn = connect(tmp_path / "t.db")
    t = ScriptedTransport([HttpResponse(429, {}, None), HttpResponse(200, {}, {"errors": [], "response": [1]})])
    assert _client(conn, t).get("fixtures").body["response"] == [1]
    rows = conn.execute("SELECT ok FROM provider_calls").fetchall()
    assert [r["ok"] for r in rows] == [0, 1]


def test_http_api_errors_and_budget(tmp_path):
    conn = connect(tmp_path / "t.db")
    t = ScriptedTransport([HttpResponse(200, {}, {"errors": {"token": "bad"}, "response": []})])
    with pytest.raises(ProviderError):
        _client(conn, t).get("fixtures")
    with pytest.raises(BudgetExceeded):
        _client(conn, ScriptedTransport([]), budget=lambda: 0).get("fixtures")


def test_api_keys_are_never_logged(tmp_path):
    conn = connect(tmp_path / "t.db")
    t = ScriptedTransport([HttpResponse(200, {"x-requests-last": "2"}, [])])
    c = ApiClient("the-odds-api", "https://x.test", {"apiKey": "SECRET123"}, conn, t, lambda: 50, auth_in_query=True, sleep=lambda s: None, clock=lambda: NOW)
    c.get("sports/x/odds", {"markets": "h2h,totals"}, expected_cost=2)
    dump = "\n".join(str(tuple(r)) for r in conn.execute("SELECT * FROM provider_calls"))
    assert "SECRET123" not in dump
    assert "apiKey=SECRET123" in t.urls[0]  # sent to the provider, but not stored


def test_budgets(tmp_path):
    conn = connect(tmp_path / "t.db")
    for _ in range(5):
        conn.execute("INSERT INTO provider_calls(provider, endpoint, http_status, ok, cost, called_at) VALUES ('api-football','f',200,1,1,?)", (NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),))
    assert api_sports_budget(conn, "api-football", 100, 10, lambda: NOW)() == 85
    b = odds_budget(conn, 500, lambda: NOW)
    assert 0 < b() <= 500 // 14 + 1  # 14 days left in November from the 17th
    conn.execute("INSERT INTO provider_calls(provider, endpoint, http_status, ok, cost, called_at, remaining) VALUES ('the-odds-api','o',200,1,40,?,0)", (NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),))
    assert b() == 0



