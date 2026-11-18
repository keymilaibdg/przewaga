"""Turn walk-forward predictions into priced markets, score them, simulate the live gate, tune parameters.

The bet simulation calls the live engine (engine.evaluate.price_market) with historical quotes, so thresholds,
quality score and the model/market blend behave exactly as in the daily pipeline.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Callable, Iterable

import numpy as np

from ..engine.evaluate import Context, Market, Quote, Selection, price_market
from ..engine.odds import fair_probabilities
from ..models import basketball as bb_model
from ..models import football as fb_model
from ..params import LeagueParams, MarketParams
from .basketball import NbaPred
from .football import FbPred

STD_PRICE = 1.909  # -110 American: archive spread/total prices are not published, standard juice assumed

# ---------------- rows ----------------


@dataclass
class Row:
    """One market of one event with model and market probabilities and the realised outcome."""

    league: str
    sport: str
    event_id: str
    label: str
    kickoff: datetime
    season: str
    market: str  # h2h | totals | spreads
    line: float | None
    keys: tuple[str, ...]
    names: tuple[str, ...]
    p_model: tuple[float, ...]
    ref: tuple[float, ...]  # reference prices (sharp / low-margin book): margin-free market probability
    best: tuple[float, ...]  # best available prices (market maximum)
    avg: tuple[float, ...] | None
    close_best: tuple[float, ...] | None
    close_ref: tuple[float, ...] | None
    outcome: int  # index of the winning selection, -1 = push / void
    n_min: float
    known: bool
    score: str
    ref_source: str = ""

    @property
    def p_fair(self) -> tuple[float, ...]:
        return tuple(fair_probabilities(list(self.ref)))

    def half_width(self, p: float) -> float:
        return fb_model.half_width_n(p, self.n_min) if self.sport == "football" else bb_model.half_width_n(p, self.n_min)


def football_rows(preds: Iterable[FbPred]) -> list[Row]:
    out = []
    for pr in preds:
        m = pr.m
        eid = f"bt:{m.league}:{m.kickoff:%Y%m%d}:{m.home}:{m.away}"
        label = f"{m.home} – {m.away}"
        score = f"{m.hg}:{m.ag}"
        res = 0 if m.hg > m.ag else 1 if m.hg == m.ag else 2
        if ("h2h", "ref") in m.odds:
            out.append(
                Row(m.league, "football", eid, label, m.kickoff, m.season, "h2h", None, ("home", "draw", "away"), (f"Wygrana {m.home}", "Remis", f"Wygrana {m.away}"),
                    pr.p, m.odds[("h2h", "ref")], m.odds[("h2h", "best")], m.odds.get(("h2h", "avg")), m.odds.get(("h2h", "close_best")), m.odds.get(("h2h", "close_ref")),
                    res, pr.n_min, pr.known, score, m.ref_source.get("h2h", ""))
            )
        if ("ou25", "ref") in m.odds:
            over = int(m.hg + m.ag > 2.5)
            out.append(
                Row(m.league, "football", eid, label, m.kickoff, m.season, "totals", 2.5, ("over", "under"), ("Powyżej 2,5 gola", "Poniżej 2,5 gola"),
                    (pr.p_over, 1 - pr.p_over), m.odds[("ou25", "ref")], m.odds[("ou25", "best")], m.odds.get(("ou25", "avg")), m.odds.get(("ou25", "close_best")),
                    m.odds.get(("ou25", "close_ref")), 0 if over else 1, pr.n_min, pr.known, score, m.ref_source.get("ou25", ""))
            )
    return out


def nba_rows(preds: Iterable[NbaPred]) -> list[Row]:
    out = []
    for pr in preds:
        g = pr.g
        eid = f"bt:nba:{g.date:%Y%m%d}:{g.home}:{g.away}"
        label = f"{g.home} – {g.away}"
        score = f"{g.hp}:{g.ap}"
        std = (STD_PRICE, STD_PRICE)
        if g.ml:
            out.append(Row("nba", "basketball", eid, label, g.date, g.season, "h2h", None, ("home", "away"), (f"Wygrana {g.home}", f"Wygrana {g.away}"),
                           (pr.p_home, 1 - pr.p_home), g.ml, g.ml, g.ml, g.ml, g.ml, 0 if g.hp > g.ap else 1, pr.n_min, pr.known, score, "SBR"))
        if g.spread_home is not None and pr.p_cover is not None:
            d = g.hp + g.spread_home - g.ap
            out.append(Row("nba", "basketball", eid, label, g.date, g.season, "spreads", g.spread_home, ("home", "away"),
                           (f"{g.home} {g.spread_home:+g}", f"{g.away} {-g.spread_home:+g}"), (pr.p_cover, 1 - pr.p_cover), std, std, std, std, std,
                           -1 if d == 0 else (0 if d > 0 else 1), pr.n_min, pr.known, score, "SBR"))
        if g.total is not None and pr.p_over is not None:
            t = g.hp + g.ap
            out.append(Row("nba", "basketball", eid, label, g.date, g.season, "totals", g.total, ("over", "under"),
                           (f"Powyżej {g.total:g} pkt", f"Poniżej {g.total:g} pkt"), (pr.p_over, 1 - pr.p_over), std, std, std, std, std,
                           -1 if t == g.total else (0 if t > g.total else 1), pr.n_min, pr.known, score, "SBR"))
    return out


# ---------------- scoring ----------------


def blend(r: Row, w: float) -> np.ndarray:
    return w * np.asarray(r.p_model) + (1 - w) * np.asarray(r.p_fair)


def log_losses(rows: list[Row], w: float) -> np.ndarray:
    return np.array([-math.log(max(blend(r, w)[r.outcome], 1e-12)) for r in rows if r.outcome >= 0])


def brier(rows: list[Row], w: float) -> float:
    vals = []
    for r in rows:
        if r.outcome < 0:
            continue
        p = blend(r, w)
        y = np.zeros(len(p))
        y[r.outcome] = 1
        vals.append(float(((p - y) ** 2).sum()))
    return float(np.mean(vals)) if vals else float("nan")


def rps(rows: list[Row], w: float) -> float:
    """Ranked probability score for ordered 1X2 outcomes (football h2h)."""
    vals = []
    for r in rows:
        if r.outcome < 0 or len(r.keys) != 3:
            continue
        p = np.cumsum(blend(r, w))[:-1]
        y = np.cumsum(np.eye(3)[r.outcome])[:-1]
        vals.append(float(((p - y) ** 2).sum() / 2))
    return float(np.mean(vals)) if vals else float("nan")


def best_weight(rows: list[Row], grid: Iterable[float] = tuple(np.round(np.arange(0, 1.0001, 0.05), 2))) -> tuple[float, dict[float, float]]:
    curve = {float(w): float(log_losses(rows, w).mean()) for w in grid}
    return min(curve, key=curve.get), curve  # type: ignore[arg-type]


def hw_scale(rows: list[Row]) -> float:
    """Scale of the model half-width so that model-vs-market disagreement is ~1 half-width on average (RMS)."""
    z = []
    for r in rows:
        for pm, pf in zip(r.p_model, r.p_fair):
            hw = r.half_width(pm)
            if hw > 0:
                z.append(((pm - pf) / hw) ** 2)
    return float(np.clip(math.sqrt(np.mean(z)), 0.5, 4.0)) if z else 1.0


def bootstrap_delta(rows: list[Row], w: float, n: int = 2000, seed: int = 7) -> dict[str, float]:
    """Paired bootstrap of mean log-loss difference (blend - market). Negative = the model adds information."""
    d = log_losses(rows, w) - log_losses(rows, 0.0)
    if len(d) == 0:
        return {"delta": float("nan"), "p_better": float("nan"), "lo": float("nan"), "hi": float("nan")}
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, len(d), (n, len(d)))].mean(axis=1)
    return {"delta": float(d.mean()), "p_better": float((means < 0).mean()), "lo": float(np.quantile(means, 0.05)), "hi": float(np.quantile(means, 0.95))}


def calibration_bins(rows: list[Row], w: float, bins: int = 10) -> list[dict[str, float]]:
    ps, ys = [], []
    for r in rows:
        if r.outcome < 0:
            continue
        p = blend(r, w)
        for i, pi in enumerate(p):
            ps.append(pi)
            ys.append(1.0 if i == r.outcome else 0.0)
    ps_a, ys_a = np.array(ps), np.array(ys)
    out = []
    for lo in np.linspace(0, 1, bins + 1)[:-1]:
        mask = (ps_a >= lo) & (ps_a < lo + 1 / bins)
        if mask.sum() >= 20:
            out.append({"predicted": float(ps_a[mask].mean()), "observed": float(ys_a[mask].mean()), "count": int(mask.sum())})
    return out


# ---------------- bet simulation (the live gate) ----------------


@dataclass
class Bet:
    row: Row
    key: str
    label: str
    price: float  # taken (best available)
    bookmaker: str
    model_prob: float
    raw_prob: float
    fair_prob: float
    ev: float
    quality: int
    risk: str
    won: bool | None  # None = push
    profit: float
    avg_price: float | None
    close_price: float | None
    close_fair: float | None  # margin-free closing probability of the selection

    @property
    def clv(self) -> float | None:
        return self.price / self.close_price - 1 if self.close_price else None

    @property
    def ev_close(self) -> float | None:
        """Expected value of the taken price against the margin-free closing line (skill measure)."""
        return self.price * self.close_fair - 1 if self.close_fair else None


def completeness(n_min: float) -> float:
    # Same formula as analysis.analyse_event: fresh odds 0.35 + injuries 0 (no free source) + history 0.35 + fixtures 0.1
    return round(0.35 + min(1.0, n_min / 15) * 0.35 + 0.1, 3)


def simulate(rows: list[Row], params: LeagueParams, per_event: int = 2) -> list[Bet]:
    by_event: dict[str, list[Row]] = {}
    for r in rows:
        by_event.setdefault(r.event_id, []).append(r)
    bets: list[Bet] = []
    for evs in by_event.values():
        r0 = evs[0]
        now = r0.kickoff - timedelta(hours=12)
        ctx = Context(now=now, kickoff=r0.kickoff, completeness=completeness(r0.n_min), both_teams_known=r0.known, params=params)
        cands = []
        for r in evs:
            sels = [
                Selection(k, nm, (r.line if k in ("home", "over") else -r.line) if (r.line is not None and r.market == "spreads") else r.line,
                          [Quote("pinnacle", rp, now), Quote("max", bp, now)], pm)
                for k, nm, pm, rp, bp in zip(r.keys, r.names, r.p_model, r.ref, r.best)
            ]
            mk = Market(r.market, r.market, r.line, sels)
            for c in price_market(mk, r.half_width, ctx):
                cands.append((c, r))
        cands.sort(key=lambda cr: (cr[0].quality, cr[0].ev), reverse=True)
        for c, r in cands[:per_event]:
            i = r.keys.index(c.sel.key)
            won = None if r.outcome < 0 else (r.outcome == i)
            close_fair = fair_probabilities(list(r.close_ref))[i] if r.close_ref else None
            bets.append(
                Bet(r, c.sel.key, c.sel.label, c.best.price, c.best.bookmaker, c.sel.model_prob, c.sel.raw_model_prob, c.sel.fair_prob, c.ev, c.quality, c.risk,
                    won, 0.0 if won is None else (c.best.price - 1 if won else -1.0), r.avg[i] if r.avg else None, r.close_best[i] if r.close_best else None, close_fair)
            )
    return bets


def summarize(bets: list[Bet]) -> dict[str, float | int | None]:
    decided = [b for b in bets if b.won is not None]
    n = len(decided)
    if n == 0:
        return {"bets": 0, "roi": None, "roi_se": None, "roi_avg_odds": None, "roi_taxed": None, "hit_rate": None, "avg_price": None, "clv": None, "ev_close": None, "profit": 0.0}
    prof = np.array([b.profit for b in decided])
    avg = [(b.avg_price - 1 if b.won else -1.0) for b in decided if b.avg_price]
    taxed = [(0.88 * b.price - 1 if b.won else -1.0) for b in decided]  # Polish 12% stake tax
    clv = [b.clv for b in decided if b.clv is not None]
    evc = [b.ev_close for b in decided if b.ev_close is not None]
    return {
        "bets": n,
        "profit": float(prof.sum()),
        "roi": float(prof.mean()),
        "roi_se": float(prof.std(ddof=1) / math.sqrt(n)) if n > 1 else None,
        "roi_avg_odds": float(np.mean(avg)) if avg else None,
        "roi_taxed": float(np.mean(taxed)),
        "hit_rate": float(np.mean([b.won for b in decided])),
        "avg_price": float(np.mean([b.price for b in decided])),
        "clv": float(np.mean(clv)) if clv else None,
        "ev_close": float(np.mean(evc)) if evc else None,
    }


# ---------------- tuning ----------------

MIN_EV_GRID = (0.02, 0.03, 0.04, 0.05, 0.06, 0.08)
MAX_DIS_GRID = (0.05, 0.08, 0.12)
MIN_TUNING_BETS = 60

# Validation rule, fixed before looking at the holdout results (see docs/BACKTEST.md):
MIN_WEIGHT = 0.10
MIN_P_BETTER = 0.80
MIN_HOLDOUT_BETS = 30


@dataclass
class MarketResult:
    market: str
    n_tune: int
    n_hold: int
    weight: float
    weight_curve: dict[float, float]
    hw_scale: float
    tune: dict[str, float]  # log-loss model / market / blend, brier, rps
    hold: dict[str, float]
    boot: dict[str, float]
    calib_raw: list[dict[str, float]]
    calib_blend: list[dict[str, float]]
    sim_hold: dict[str, float | int | None] = field(default_factory=dict)
    status: str = "validating"
    reason: str = ""


def scores(rows: list[Row], w: float) -> dict[str, float]:
    if not rows:
        return {}
    out = {
        "logloss_model": float(log_losses(rows, 1.0).mean()),
        "logloss_market": float(log_losses(rows, 0.0).mean()),
        "logloss_blend": float(log_losses(rows, w).mean()),
        "brier_model": brier(rows, 1.0),
        "brier_market": brier(rows, 0.0),
        "brier_blend": brier(rows, w),
    }
    if rows[0].market == "h2h" and len(rows[0].keys) == 3:
        out |= {"rps_model": rps(rows, 1.0), "rps_market": rps(rows, 0.0), "rps_blend": rps(rows, w)}
    return out


def tune_market(market: str, tune: list[Row], hold: list[Row]) -> MarketResult:
    w, curve = best_weight(tune) if tune else (0.0, {})
    k = hw_scale(tune) if tune else 1.0
    return MarketResult(market, len(tune), len(hold), w, curve, k, scores(tune, w), scores(hold, w), bootstrap_delta(hold, w),
                        calibration_bins(hold, 1.0), calibration_bins(hold, w))


def tune_thresholds(rows: list[Row], base: LeagueParams) -> tuple[LeagueParams, list[dict[str, float]]]:
    """min_ev / max_disagreement maximising (ROI - 1 SE) on the tuning period; all markets allowed while tuning."""
    grid = []
    best, best_score = base, -math.inf
    for me in MIN_EV_GRID:
        for md in MAX_DIS_GRID:
            p = replace(base, min_ev=me, max_disagreement=md)
            s = summarize(simulate(rows, p))
            score = (s["roi"] - (s["roi_se"] or 0)) if s["bets"] >= MIN_TUNING_BETS and s["roi"] is not None else -math.inf  # type: ignore[operator]
            grid.append({"min_ev": me, "max_disagreement": md, "bets": s["bets"], "roi": s["roi"], "roi_se": s["roi_se"]})
            if score > best_score:
                best, best_score = p, score
    return best, grid


def decide(mr: MarketResult) -> tuple[str, str]:
    s, b = mr.sim_hold, mr.boot
    if mr.n_tune == 0 or mr.n_hold == 0:
        return "validating", "za mało historii z kursami do walidacji"
    if mr.weight < MIN_WEIGHT:
        return "validating", f"optymalna waga modelu {mr.weight:.2f} — rynek bez marży prognozuje lepiej"
    if not (b["delta"] < 0 and b["p_better"] >= MIN_P_BETTER):
        return "validating", f"na okresie testowym model nie poprawia prognozy rynku (Δ log-loss {b['delta']:+.4f}, P={b['p_better']:.2f})"
    if (s.get("bets") or 0) < MIN_HOLDOUT_BETS:
        return "validating", f"za mało typów na okresie testowym ({s.get('bets') or 0} < {MIN_HOLDOUT_BETS})"
    if (s.get("roi") or 0) < 0:
        return "validating", f"ujemny zwrot typów na okresie testowym (ROI {100 * (s.get('roi') or 0):+.1f}%)"
    return "validated", f"Δ log-loss {b['delta']:+.4f} (P={b['p_better']:.2f}), {s['bets']} typów, ROI {100 * s['roi']:+.1f}%"


def league_params(league: str, results: dict[str, MarketResult], thresholds: LeagueParams, xi: float, now: str) -> LeagueParams:
    markets = {m: MarketParams(model_weight=r.weight, hw_scale=round(r.hw_scale, 3), status=r.status, reason=r.reason) for m, r in results.items()}
    status = "validated" if any(r.status == "validated" for r in results.values()) else "validating"
    reasons = "; ".join(f"{m}: {r.reason}" for m, r in results.items())
    return replace(thresholds, league_key=league, status=status, reason=reasons, markets=markets, xi=xi, calibrated_at=now)


def split(rows: list[Row], cutoff: datetime) -> tuple[list[Row], list[Row]]:
    return [r for r in rows if r.kickoff < cutoff], [r for r in rows if r.kickoff >= cutoff]


def by_market(rows: list[Row]) -> dict[str, list[Row]]:
    out: dict[str, list[Row]] = {}
    for r in rows:
        out.setdefault(r.market, []).append(r)
    return out


def apply_market_params(rows: list[Row], base: LeagueParams, results: dict[str, MarketResult], allow_all: bool = True) -> LeagueParams:
    """Params with the tuned weight / hw_scale per market; status 'validated' everywhere while simulating."""
    markets = {m: MarketParams(model_weight=r.weight, hw_scale=r.hw_scale, status="validated" if allow_all else r.status) for m, r in results.items()}
    return replace(base, markets=markets)


Clock = Callable[[], datetime]
