"""Backtest orchestration: data -> walk-forward predictions -> tuning -> validation -> calibration files.

  python -m app.backtest run       full backtest + calibration (monthly / by hand)
  python -m app.backtest ratings   only refresh the cup ratings (weekly)

Outputs (committed by the workflow):
  app/calibration.json        per-league parameters read by the daily pipeline
  app/cup_ratings.json        cross-league team ratings for the UEFA cups
  backtest/results.json       all metrics
  backtest/backtest.json      simulated out-of-sample bets for the app (Statystyki -> Backtest)
  ../docs/BACKTEST.md         human-readable report (Polish)
"""
from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from ..config import DB_PATH, LEAGUE_BY_KEY, ROOT, season_for
from ..models import basketball as bb_model
from ..models import cups as cm
from ..models import football as fb_model
from ..params import CALIBRATION_PATH, LeagueParams, MarketParams
from ..providers.http import iso
from . import cups as cup_data
from . import evaluate as E
from . import prices
from .basketball import walk_forward as nba_wf
from .data import FbMatch, NbaGame, SourceError, cups, fd_extra, fd_season, sbr_season
from .football import walk_forward as fb_wf

log = logging.getLogger("przewaga.backtest")

OUT_DIR = ROOT / "pipeline" / "backtest"
PRICE_BUCKETS_PATH = ROOT / "pipeline" / "app" / "price_buckets.json"
REPORT = ROOT / "docs" / "BACKTEST.md"

FOOTBALL = {"epl": "E0", "laliga": "SP1", "bundesliga": "D1", "ekstraklasa": "POL"}
FIRST_SEASON = 2019  # 2019/20: first season with market maximum columns (MaxH) in the files
FB_HOLDOUT = datetime(2025, 7, 1, tzinfo=timezone.utc)  # 2025/26 + current season: never used for tuning
FB_XI = (0.0010, 0.0019, 0.0035)

NBA_SEASONS = ("2019-2020", "2020-2021", "2021-2022", "2022-2023")
NBA_HOLDOUT = datetime(2022, 7, 1, tzinfo=timezone.utc)  # 2022/23 season
NBA_XI = (0.004, 0.008, 0.015)

CUP_HOLDOUT = datetime(2024, 7, 1, tzinfo=timezone.utc)  # cups 2024/25 predicted from data before the season


def _r(x: float | None, d: int = 4) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), d)


# ---------------- football ----------------


def football_matches(now: datetime, offline: bool) -> tuple[dict[str, list[FbMatch]], list[str]]:
    cur = int(season_for("football", now))
    out: dict[str, list[FbMatch]] = {}
    skipped: list[str] = []
    for key, code in FOOTBALL.items():
        ms: list[FbMatch] = []
        if code == "POL":
            try:
                ms = [m for m in fd_extra("POL", key, offline) if int(m.season) >= FIRST_SEASON]
            except SourceError as e:
                skipped.append(str(e))
        else:
            for y in range(FIRST_SEASON, cur + 1):
                try:
                    ms += fd_season(code, y, key, cur, offline)
                except SourceError as e:
                    skipped.append(str(e))
        out[key] = ms
    return out, skipped


def run_football(now: datetime, offline: bool) -> tuple[dict, dict[str, LeagueParams], list[E.Bet], list[str]]:
    data, skipped = football_matches(now, offline)
    # 1) walk-forward for each decay value; choose the decay on the tuning period (raw model, 1X2 log-loss)
    rows_by_xi: dict[float, dict[str, list[E.Row]]] = {}
    for xi in FB_XI:
        rows_by_xi[xi] = {k: E.football_rows(fb_wf(ms, xi)) for k, ms in data.items()}
        log.info("football xi=%s: %s", xi, {k: len(v) for k, v in rows_by_xi[xi].items()})
    xi_ll = {}
    for xi, by_lg in rows_by_xi.items():
        tune = [r for rows in by_lg.values() for r in rows if r.market == "h2h" and r.kickoff < FB_HOLDOUT]
        xi_ll[xi] = float(E.log_losses(tune, 1.0).mean()) if tune else math.inf
    xi = min(xi_ll, key=xi_ll.get)  # type: ignore[arg-type]
    report = {"xi_grid": {str(k): _r(v, 5) for k, v in xi_ll.items()}, "xi": xi, "leagues": {}, "skipped": skipped}
    params: dict[str, LeagueParams] = {}
    bets_out: list[E.Bet] = []
    for lg, rows in rows_by_xi[xi].items():
        p, rep, bets = calibrate_league(lg, rows, FB_HOLDOUT, xi, now)
        params[lg], report["leagues"][lg] = p, rep
        bets_out += bets
    # every match with odds (not only those the model could predict) for the price history
    report["price_buckets"] = {lg: prices.summary(E.football_rows(_market_only_preds(ms)), "football-data.co.uk, kurs średni przed meczem" + (" (zamknięcie)" if lg == "ekstraklasa" else ""))
                               for lg, ms in data.items()}
    return report, params, bets_out, skipped


def _market_only_preds(ms: list[FbMatch]) -> list:
    """Wrap matches as predictions without a model (price history needs only odds and results)."""
    from .football import FbPred

    return [FbPred(m, m.kickoff, (1 / 3, 1 / 3, 1 / 3), 0.5, 1.0, 1.0, 0.0, False) for m in ms]


def calibrate_league(lg: str, rows: list[E.Row], cutoff: datetime, xi: float, now: datetime) -> tuple[LeagueParams, dict, list[E.Bet]]:
    tune, hold = E.split(rows, cutoff)
    tm, hm = E.by_market(tune), E.by_market(hold)
    results = {m: E.tune_market(m, tm.get(m, []), hm.get(m, [])) for m in sorted(set(tm) | set(hm))}
    base = E.apply_market_params(tune, LeagueParams(lg), results)
    thresholds, grid = E.tune_thresholds(tune, base)
    hold_bets = E.simulate(hold, thresholds)
    for m, mr in results.items():
        mr.sim_hold = E.summarize([b for b in hold_bets if b.row.market == m])
        mr.status, mr.reason = E.decide(mr)
    p = E.league_params(lg, results, thresholds, xi, iso(now))
    rep = {
        "rows_tune": len(tune),
        "rows_hold": len(hold),
        "seasons": sorted({r.season for r in rows}),
        "ref_sources": sorted({r.ref_source for r in rows}),
        "closing_only": any(r.ref_source.endswith("C") for r in rows),
        "min_ev": thresholds.min_ev,
        "max_disagreement": thresholds.max_disagreement,
        "threshold_grid": grid,
        "sim_tune": E.summarize(E.simulate(tune, thresholds)),
        "sim_hold": E.summarize(hold_bets),
        "markets": {m: _market_report(mr) for m, mr in results.items()},
        "status": p.status,
    }
    return p, rep, hold_bets


def _market_report(mr: E.MarketResult) -> dict:
    d = asdict(mr)
    d["weight_curve"] = {str(k): _r(v, 5) for k, v in mr.weight_curve.items()}
    d["hw_scale"] = _r(mr.hw_scale, 3)
    return d


# ---------------- NBA ----------------


def run_nba(now: datetime, offline: bool) -> tuple[dict, LeagueParams | None, list[E.Bet]]:
    games: list[NbaGame] = []
    skipped = []
    for s in NBA_SEASONS:
        try:
            gs = sbr_season(s, offline)
            log.info("SBR %s: %d games", s, len(gs))
            games += gs
        except SourceError as e:
            skipped.append(str(e))
    if len(games) < 500:
        return {"skipped": skipped, "error": "za mało meczów z archiwum kursów"}, None, []
    def tune_ll(rows: list[E.Row], markets: tuple[str, ...] = ("h2h",)) -> float:
        t = [r for r in rows if r.market in markets and r.kickoff < NBA_HOLDOUT]
        return float(E.log_losses(t, 1.0).mean()) if t else math.inf

    rows_by_xi = {xi: E.nba_rows(nba_wf(games, xi)) for xi in NBA_XI}
    xi_ll = {xi: tune_ll(rows) for xi, rows in rows_by_xi.items()}
    xi = min(xi_ll, key=xi_ll.get)  # type: ignore[arg-type]
    # schedule features (rest, back-to-back, travel): kept only if they improve the raw model on the tuning period
    rows_fat = E.nba_rows(nba_wf(games, xi, fatigue=True))
    fat_ll = {"bez": {m: _r(tune_ll(rows_by_xi[xi], (m,)), 5) for m in ("h2h", "spreads", "totals")},
              "z": {m: _r(tune_ll(rows_fat, (m,)), 5) for m in ("h2h", "spreads", "totals")}}
    use_fatigue = tune_ll(rows_fat, ("h2h", "spreads")) < tune_ll(rows_by_xi[xi], ("h2h", "spreads"))
    rows = rows_fat if use_fatigue else rows_by_xi[xi]
    p, rep, bets = calibrate_league("nba", rows, NBA_HOLDOUT, xi, now)
    p = replace(p, fatigue=use_fatigue)
    rep["fatigue"] = {"used": use_fatigue, "tune_logloss": fat_ll, "coefficients": _fatigue_coefs(games, xi)}
    preds = nba_wf(games, xi, fatigue=use_fatigue)
    hold = [pr for pr in preds if pr.g.date >= NBA_HOLDOUT]
    if hold:  # are the normal-distribution widths right? (share of games inside +-1 sigma should be ~68%)
        zm = np.array([(pr.g.hp - pr.g.ap - pr.margin) / pr.sigma_m for pr in hold])
        zt = np.array([(pr.g.hp + pr.g.ap - pr.total) / pr.sigma_t for pr in hold])
        rep["sigma_check"] = {"margin_within_1sigma": _r(float((abs(zm) < 1).mean()), 3), "total_within_1sigma": _r(float((abs(zt) < 1).mean()), 3),
                              "margin_z_sd": _r(float(zm.std()), 3), "total_z_sd": _r(float(zt.std()), 3), "total_bias": _r(float((zt * np.array([pr.sigma_t for pr in hold])).mean()), 2)}
    rep |= {"xi_grid": {str(k): _r(v, 5) for k, v in xi_ll.items()}, "xi": xi, "skipped": skipped, "games": len(games), "price_note": "spread/total: -110 (1.909) assumed"}
    rep["price_buckets"] = prices.summary(E.nba_rows(_market_only_nba(games)), "sportsbookreviewsonline, moneyline zamknięcia")
    return rep, p, bets


def _market_only_nba(games: list[NbaGame]) -> list:
    from .basketball import NbaPred

    return [NbaPred(g, g.date, 0.0, 0.0, 0.5, None, None, 12.0, 18.0, 0.0, False) for g in games]


def _fatigue_coefs(games: list[NbaGame], xi: float) -> dict[str, float]:
    """Schedule coefficients fitted on all archive games (points of home margin; for the report)."""
    from ..models.basketball import Game, Ratings
    from ..models.schedule import contexts

    from .basketball import key

    gs = sorted(games, key=lambda g: g.date)
    ctx = contexts([(key(g), g.date, g.home, g.away, g.home) for g in gs])
    end = gs[-1].date
    m = Ratings.fit([Game(g.home, g.away, g.hp, g.ap, (end - g.date).total_seconds() / 86400, ctx[key(g)]) for g in gs], xi=0.0005, fatigue=True)
    return {k: round(v, 2) for k, v in m.fatigue.items()} | {"pts_own_b2b": round(m.fatigue_pts[0], 2), "pts_opp_b2b": round(m.fatigue_pts[1], 2)}


# ---------------- cups ----------------


def run_cups(now: datetime, offline: bool, db: sqlite3.Connection | None, validate: bool = True) -> tuple[dict, dict | None]:
    key = os.environ.get("APISPORTS_KEY")
    cm_list = cups(key, offline)
    if not cm_list:
        return {"error": f"brak meczów pucharowych (API-Football 2022-2024; klucz {'jest' if key else 'BRAK'})"}, None
    ds = cup_data.build(now, cm_list, db, offline)
    rep: dict = {"cup_matches": len(ds.cup_rows), "teams": len(ds.entries), "domestic_matches": len(ds.matches) - len(ds.cup_rows), "skipped": ds.skipped}
    if validate:
        r = cup_data.fit_at(ds, CUP_HOLDOUT)
        train_cup = [c for c in ds.cup_rows if c[0] < CUP_HOLDOUT]
        freq = np.bincount([0 if c[3] > c[4] else 1 if c[3] == c[4] else 2 for c in train_cup], minlength=3) / max(1, len(train_cup))
        ll_m, ll_b, rows = [], [], []
        for ko, hk, ak, hg, ag, neutral in ds.cup_rows:
            if not (CUP_HOLDOUT <= ko < CUP_HOLDOUT + timedelta(days=365)) or not (cup_data.known(r, hk) and cup_data.known(r, ak)):
                continue
            lam, mu = cm.rates(r, hk, ak, neutral)  # type: ignore[misc]
            o = fb_model.outcome_probs(fb_model.score_matrix(lam, mu, r["rho"]))
            p = np.array([o["home"], o["draw"], o["away"]])
            y = 0 if hg > ag else 1 if hg == ag else 2
            ll_m.append(-math.log(p[y]))
            ll_b.append(-math.log(freq[y]))
            rows.append((p, y))
        bins = []
        ps = np.array([pp for p, _ in rows for pp in p]) if rows else np.array([])
        ys = np.array([1.0 if i == y else 0.0 for p, y in rows for i in range(3)]) if rows else np.array([])
        for lo in np.linspace(0, 1, 11)[:-1]:
            mask = (ps >= lo) & (ps < lo + 0.1)
            if mask.sum() >= 20:
                bins.append({"predicted": _r(float(ps[mask].mean()), 3), "observed": _r(float(ys[mask].mean()), 3), "count": int(mask.sum())})
        rep["validation"] = {
            "season": "2024/25 (wszystkie fazy, model z danych sprzed 1.07.2024)",
            "matches": len(ll_m),
            "logloss_model": _r(float(np.mean(ll_m))) if ll_m else None,
            "logloss_baseline": _r(float(np.mean(ll_b))) if ll_b else None,
            "baseline": "częstości 1/X/2 z meczów pucharowych 2022-2024",
            "calibration": bins,
        }
    ratings = cup_data.fit_at(ds, now)
    ratings |= {"fitted_at": iso(now), "matches": len(ds.matches)}
    return rep, ratings


# ---------------- outputs ----------------


def history_entry(b: E.Bet) -> dict:
    r = b.row
    lg = LEAGUE_BY_KEY.get(r.league)
    mtype = {("football", "h2h"): "1X2", ("football", "totals"): "TOTAL_GOALS", ("basketball", "h2h"): "MONEYLINE", ("basketball", "totals"): "TOTAL_POINTS", ("basketball", "spreads"): "SPREAD"}[(r.sport, r.market)]
    return {
        "id": f"{r.event_id}:{r.market}:{b.key}",
        "origin": "live",
        "sport": r.sport,
        "eventLabel": r.label,
        "league": lg.name if lg else r.league,
        "kickoff": iso(r.kickoff),
        "market": mtype,
        "label": b.label,
        "bookmaker": "Najlepszy kurs rynku" if b.bookmaker == "max" else "Kurs referencyjny",
        "openingPrice": round(b.price, 3),
        "closingPrice": round(b.close_price, 3) if b.close_price else None,
        "clv": _r(b.clv),
        "modelProb": round(b.model_prob, 4),
        "ev": round(b.ev, 4),
        "quality": b.quality,
        "risk": b.risk,
        "generatedAt": iso(r.kickoff - timedelta(hours=12)),
        "result": "void" if b.won is None else ("won" if b.won else "lost"),
        "finalScore": r.score,
        "profit": round(b.profit, 4),
    }


def write_outputs(now: datetime, fb: dict, fb_params: dict[str, LeagueParams], nba: dict, nba_params: LeagueParams | None, cups_rep: dict, ratings: dict | None, bets: list[E.Bet]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    leagues: dict[str, dict] = {}
    for p in [*fb_params.values(), *([nba_params] if nba_params else [])]:
        leagues[p.league_key] = {
            "status": p.status,
            "reason": p.reason,
            "min_ev": p.min_ev,
            "min_quality": p.min_quality,
            "max_disagreement": p.max_disagreement,
            "xi": p.xi,
            "fatigue": p.fatigue,
            "markets": {m: asdict(mp) for m, mp in p.markets.items()},
        }
    cup_reason = "ratingi międzyligowe; brak darmowej historii kursów pucharowych — waga jak w ligach krajowych, walidacja na kursach zbieranych na bieżąco"
    for key in ("ucl", "uel"):
        if ratings:
            mk = {}
            for m in ("h2h", "totals"):
                ws = sorted(p.markets[m].model_weight for p in fb_params.values() if m in p.markets)
                w = ws[len(ws) // 2] if ws else 0.5
                mk[m] = asdict(MarketParams(w, 1.0, "validating", cup_reason))
            leagues[key] = {"status": "validating", "reason": cup_reason, "markets": mk}
    leagues["euroleague"] = {"status": "market_only", "reason": "brak darmowego źródła wyników Euroligi do modelu"}
    calib = {"generated_at": iso(now), "source": "python -m app.backtest run", "leagues": leagues}
    CALIBRATION_PATH.write_text(json.dumps(calib, ensure_ascii=False, indent=2), encoding="utf-8")
    if ratings:
        cm.RATINGS_PATH.write_text(json.dumps(ratings, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    buckets = dict(fb.get("price_buckets") or {})
    if nba.get("price_buckets"):
        buckets["nba"] = nba["price_buckets"]
    PRICE_BUCKETS_PATH.write_text(json.dumps({"generated_at": iso(now), "leagues": buckets}, ensure_ascii=False, indent=1), encoding="utf-8")
    results = {"generated_at": iso(now), "football": fb, "nba": nba, "cups": cups_rep}
    (OUT_DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    entries = sorted((history_entry(b) for b in bets), key=lambda e: e["kickoff"], reverse=True)
    (OUT_DIR / "backtest.json").write_text(json.dumps(entries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    from .report import markdown

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(markdown(results, calib), encoding="utf-8")


def open_db() -> sqlite3.Connection | None:
    if not Path(DB_PATH).exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def run(offline: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    fb, fb_params, fb_bets, _ = run_football(now, offline)
    nba, nba_params, nba_bets = run_nba(now, offline)
    db = open_db()
    try:
        cups_rep, ratings = run_cups(now, offline, db)
    except SourceError as e:
        cups_rep, ratings = {"error": str(e)}, None
    write_outputs(now, fb, fb_params, nba, nba_params, cups_rep, ratings, fb_bets + nba_bets)
    return {
        "football": {k: v["status"] for k, v in fb["leagues"].items()},
        "nba": nba_params.status if nba_params else None,
        "cups": {k: v for k, v in cups_rep.items() if k in ("error", "cup_matches", "teams", "domestic_matches", "validation")},
        "skipped": fb.get("skipped", []) + nba.get("skipped", []) + cups_rep.get("skipped", []),
    }


def ratings_only(offline: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    db = open_db()
    rep, ratings = run_cups(now, offline, db, validate=False)
    if ratings:
        cm.RATINGS_PATH.write_text(json.dumps(ratings, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {k: v for k, v in rep.items() if k != "skipped"} | {"skipped": len(rep.get("skipped", []))}


__all__ = ["run", "ratings_only", "replace", "bb_model"]
