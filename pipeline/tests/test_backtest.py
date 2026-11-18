"""Backtest end-to-end on synthetic archives (offline cache), plus the leakage guard of the walk-forward."""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import params as params_mod
from app.backtest import data as D
from app.backtest import evaluate as E
from app.backtest import run as R
from app.backtest.football import walk_forward
from app.models import cups as cm

NOW = datetime(2026, 11, 18, 9, 0, tzinfo=timezone.utc)
FD_HEADER = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,PSH,PSD,PSA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,P>2.5,P<2.5,Max>2.5,Max<2.5,Avg>2.5,Avg<2.5,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,AvgCH,AvgCD,AvgCA"


def _poisson(rng: random.Random, lam: float) -> int:
    k, p, l_ = 0, 1.0, math.exp(-lam)
    while True:
        p *= rng.random()
        if p <= l_:
            return k
        k += 1


def _odds(probs: list[float], margin: float) -> list[float]:
    return [round(1 / (p * (1 + margin)), 2) for p in probs]


def _season_csv(rng: random.Random, code: str, year: int, teams: dict[str, float], n_rounds: int = 18) -> str:
    lines = [FD_HEADER]
    names = list(teams)
    d0 = datetime(year, 8, 15)
    for rnd in range(n_rounds):
        rng.shuffle(names)
        day = d0 + timedelta(days=7 * rnd)
        for i in range(0, len(names), 2):
            h, a = names[i], names[i + 1]
            lam, mu = math.exp(0.3 + teams[h] - teams[a] * 0.6), math.exp(0.05 + teams[a] - teams[h] * 0.6)
            hg, ag = _poisson(rng, lam), _poisson(rng, mu)
            # market probabilities from the true strengths + noise
            ph = min(0.85, max(0.08, 0.45 + 0.5 * (teams[h] - teams[a]) + rng.gauss(0, 0.03)))
            pd = 0.26
            pa = max(0.05, 1 - ph - pd)
            po = min(0.8, max(0.2, 0.52 + 0.2 * (lam + mu - 2.6)))
            ps, mx, av = _odds([ph, pd, pa], 0.025), _odds([ph, pd, pa], -0.01), _odds([ph, pd, pa], 0.05)
            o_ps, o_mx, o_av = _odds([po, 1 - po], 0.025), _odds([po, 1 - po], -0.01), _odds([po, 1 - po], 0.05)
            row = [code, day.strftime("%d/%m/%Y"), "15:00", h, a, str(hg), str(ag), "H" if hg > ag else "D" if hg == ag else "A", *map(str, ps + mx + av + o_ps + o_mx + o_av + ps + mx + av)]
            lines.append(",".join(row))
    return "\n".join(lines) + "\n"


def _sbr_html(rng: random.Random, season: str, teams: dict[str, float]) -> str:
    start = int(season[:4])
    rows = ["<tr><th>Date</th><th>Rot</th><th>VH</th><th>Team</th><th>1st</th><th>2nd</th><th>3rd</th><th>4th</th><th>Final</th><th>Open</th><th>Close</th><th>ML</th><th>2H</th></tr>"]
    names = list(teams)
    for k in range(160):
        day = datetime(start, 10, 20) + timedelta(days=k)
        rng.shuffle(names)
        for i in range(0, 6, 2):
            v, h = names[i], names[i + 1]
            margin = 2.5 + teams[h] - teams[v] + rng.gauss(0, 12)
            tot = 220 + rng.gauss(0, 18)
            hp, vp = int(round((tot + margin) / 2)), int(round((tot - margin) / 2))
            if hp == vp:
                hp += 1
            sp = round((2.5 + teams[h] - teams[v]) * 2) / 2
            ph = 1 / (1 + math.exp(-sp / 6))
            ml = lambda p: str(int(-100 * p / (1 - p))) if p > 0.5 else str(int(100 * (1 - p) / p))  # noqa: E731
            fav_home = sp >= 0
            vclose, hclose = ("220.5", str(abs(sp))) if fav_home else (str(abs(sp)), "220.5")
            mmdd = day.strftime("%m%d").lstrip("0")
            rows.append(f"<tr><td>{mmdd}</td><td>501</td><td>V</td><td>{v}</td><td>1</td><td>1</td><td>1</td><td>1</td><td>{vp}</td><td>0</td><td>{vclose}</td><td>{ml(min(0.95, max(0.05, 1 - ph + 0.02)))}</td><td>1</td></tr>")
            rows.append(f"<tr><td>{mmdd}</td><td>502</td><td>H</td><td>{h}</td><td>1</td><td>1</td><td>1</td><td>1</td><td>{hp}</td><td>0</td><td>{hclose}</td><td>{ml(min(0.95, max(0.05, ph + 0.02)))}</td><td>1</td></tr>")
    return "<table>" + "".join(rows) + "</table>"


@pytest.fixture()
def archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    rng = random.Random(3)
    cache = tmp_path / "cache"
    (cache / "fd").mkdir(parents=True)
    (cache / "sbr").mkdir()
    leagues = {"E0": "epl", "SP1": "laliga"}
    for code in leagues:
        teams = {f"{code}team{i}": rng.gauss(0, 0.35) for i in range(12)}
        for y in range(2023, 2027):
            (cache / "fd" / f"{D.season_code(y)}_{code}.csv").write_text(_season_csv(rng, code, y, teams), encoding="utf-8")
    nba = {t: rng.gauss(0, 5) for t in ["Boston", "Miami", "Denver", "Utah", "Phoenix", "Dallas", "Chicago", "Detroit", "Orlando", "Atlanta"]}
    for s in ("2019-20", "2020-21", "2021-22", "2022-23"):
        (cache / "sbr" / f"nba_{s}.html").write_text(_sbr_html(rng, s, nba), encoding="utf-8")
    monkeypatch.setattr(D, "CACHE", cache)
    monkeypatch.setattr(D, "CUPS_FILE", tmp_path / "cups.json")
    monkeypatch.setattr(R, "FOOTBALL", {"epl": "E0", "laliga": "SP1"})
    monkeypatch.setattr(R, "FIRST_SEASON", 2023)
    monkeypatch.setattr(R, "FB_XI", (0.0019,))
    monkeypatch.setattr(R, "NBA_XI", (0.008,))
    monkeypatch.setattr(R, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(R, "REPORT", tmp_path / "BACKTEST.md")
    monkeypatch.setattr(R, "CALIBRATION_PATH", tmp_path / "calibration.json")
    monkeypatch.setattr(R, "PRICE_BUCKETS_PATH", tmp_path / "price_buckets.json")
    monkeypatch.setattr(cm, "RATINGS_PATH", tmp_path / "cup_ratings.json")
    monkeypatch.setattr(R, "open_db", lambda: None)
    return tmp_path


def test_backtest_end_to_end(archive: Path) -> None:
    out = R.run(offline=True, now=NOW)
    assert set(out["football"]) == {"epl", "laliga"}
    calib = json.loads((archive / "calibration.json").read_text())
    for lg in ("epl", "laliga", "nba"):
        d = calib["leagues"][lg]
        assert d["status"] in ("validated", "validating")
        for m in d["markets"].values():
            assert 0 <= m["model_weight"] <= 1 and m["hw_scale"] > 0
    assert calib["leagues"]["euroleague"]["status"] == "market_only"
    res = json.loads((archive / "out" / "results.json").read_text())
    epl = res["football"]["leagues"]["epl"]
    assert epl["rows_hold"] > 0 and epl["rows_tune"] > 0
    assert "markets" in res["nba"]
    # synthetic market is built from the true strengths -> the market must forecast at least as well as the model
    h = epl["markets"]["h2h"]["hold"]
    assert h["logloss_market"] < h["logloss_model"] + 0.05
    bets = json.loads((archive / "out" / "backtest.json").read_text())
    for b in bets:
        assert b["result"] in ("won", "lost", "void") and b["ev"] >= 0.02 - 1e-9
    report = (archive / "BACKTEST.md").read_text()
    assert "Werdykt" in report and "Premier League" in report
    # the daily pipeline reads the produced file
    loaded = params_mod.load(archive / "calibration.json")
    assert loaded["epl"].markets["h2h"].model_weight == calib["leagues"]["epl"]["markets"]["h2h"]["model_weight"]
    assert loaded["ucl"].status == "market_only"  # no cup data in this synthetic archive


def test_walk_forward_uses_only_past_matches() -> None:
    rng = random.Random(1)
    teams = {f"t{i}": rng.gauss(0, 0.3) for i in range(10)}
    text = _season_csv(rng, "E0", 2024, teams, n_rounds=48)
    ms = D.parse_fd(text, "epl")
    preds = walk_forward(ms)
    assert preds
    for p in preds:
        assert p.as_of <= p.m.kickoff
    # changing a future result must not change any earlier prediction
    cut = preds[len(preds) // 2]
    later = [m for m in ms if m.kickoff >= cut.as_of]
    later[-1].hg += 5
    again = {(p.m.home, p.m.away, p.m.kickoff): p.p for p in walk_forward(ms)}
    assert again[(cut.m.home, cut.m.away, cut.m.kickoff)] == pytest.approx(cut.p)


def test_parse_sbr_lines() -> None:
    html = (
        "<tr><td>1019</td><td>501</td><td>V</td><td>Brooklyn</td><td>1</td><td>1</td><td>1</td><td>1</td><td>104</td><td>240.5</td><td>233.5</td><td>105</td><td>2</td></tr>"
        "<tr><td>1019</td><td>502</td><td>H</td><td>Milwaukee</td><td>1</td><td>1</td><td>1</td><td>1</td><td>127</td><td>pk</td><td>1.5</td><td>-125</td><td>114</td></tr>"
        "<tr><td>1019</td><td>503</td><td>V</td><td>GoldenState</td><td>1</td><td>1</td><td>1</td><td>1</td><td>121</td><td>230.5</td><td>3.5</td><td>140</td><td>2</td></tr>"
        "<tr><td>1019</td><td>504</td><td>H</td><td>LALakers</td><td>1</td><td>1</td><td>1</td><td>1</td><td>114</td><td>4.5</td><td>226.5</td><td>-160</td><td>1</td></tr>"
    )
    g1, g2 = D.parse_sbr(html, "2021-2022")
    assert (g1.home, g1.away, g1.hp, g1.ap) == ("MIL", "BKN", 127, 104)
    assert g1.total == 233.5 and g1.spread_home == -1.5
    assert g1.ml == (pytest.approx(1.8), pytest.approx(2.05))
    assert g2.total == 226.5 and g2.spread_home == 3.5  # visitor favourite by 3.5
    assert g1.date.year == 2021 and g1.date.month == 10


def test_parse_fd_falls_back_without_pinnacle() -> None:
    text = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,BFEH,BFED,BFEA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA\nE0,21/08/2026,20:00,Arsenal,Coventry,3,0,1.25,6.4,13.5,1.3,7.0,15.0,1.22,6.0,11.0\n"
    (m,) = D.parse_fd(text, "epl")
    assert m.ref_source["h2h"] == "BFE"
    assert m.odds[("h2h", "best")] == (1.3, 7.0, 11.0)  # 15.0 is >25% above the average 11.0: data error, average used
