"""Price every available market of an event and decide which selections (if any) are recommendable.

Rules (hard): EV >= min_ev, quality >= min_quality, price <= MAX_PRICE, half-point lines only (no pushes),
fresh odds, model has data on both teams, and the league/market was validated by the backtest (app/params.py).
Missing data lowers quality; it never raises it. Thresholds and the model/market weight come per league from
app/calibration.json (ETAP 5); the same function is used by the backtest, so live and backtest gate identically.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from ..config import (
    MARKET_MAX_OVER_MEDIAN,
    MARKET_MAX_PRICE,
    MARKET_MAX_REF_MARGIN,
    MARKET_MIN_BOOKS,
    MARKET_MIN_EV,
    MAX_ODDS_AGE_H,
    MAX_PRICE,
)
from ..params import LeagueParams
from .odds import expected_value, fair_probabilities, implied_probability, overround


@dataclass
class Quote:
    bookmaker: str
    price: float
    captured_at: datetime


@dataclass
class Selection:
    key: str  # home | draw | away | over | under
    label: str
    line: float | None
    quotes: list[Quote]
    raw_model_prob: float
    model_prob: float = 0.0  # blended with market
    prob_low: float = 0.0
    prob_high: float = 0.0
    fair_prob: float = 0.0
    history: list[tuple[datetime, float]] = field(default_factory=list)

    @property
    def best(self) -> Quote | None:
        return max(self.quotes, key=lambda q: q.price) if self.quotes else None


@dataclass
class Market:
    market: str  # h2h | totals | spreads
    name: str
    line: float | None
    selections: list[Selection]
    margin: float | None = None
    verdict: str = ""
    ref_book: str | None = None  # book whose margin-free prices are the reference


@dataclass
class Candidate:
    market: Market
    sel: Selection
    best: Quote
    ev: float
    implied: float
    quality: int
    risk: str
    hw: float
    kind: str = "model"  # model | market (price above the margin-free reference, no model involved)
    books: int = 0
    median: float | None = None


@dataclass
class Context:
    now: datetime
    kickoff: datetime
    completeness: float  # 0..1: share of data sources available for this event
    both_teams_known: bool
    lineups_confirmed: bool = False
    params: LeagueParams = field(default_factory=lambda: LeagueParams("default"))


def fmt_pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%".replace(".", ",")


def fmt_signed(x: float, d: int = 1) -> str:
    return ("+" if x > 0 else "−" if x < 0 else "") + fmt_pct(abs(x), d)


def price_market(mk: Market, half_width: Callable[[float], float], ctx: Context) -> list[Candidate]:
    """Fill fair/blended probabilities and return recommendable candidates (unsorted)."""
    fresh_cut = ctx.now - timedelta(hours=MAX_ODDS_AGE_H)
    # Reference: margin-free probabilities from the book with the lowest overround among complete sets.
    by_book: dict[str, list[float]] = {}
    for s in mk.selections:
        for q in s.quotes:
            by_book.setdefault(q.bookmaker, []).append(q.price)
    complete = {b: ps for b, ps in by_book.items() if len(ps) == len(mk.selections)}
    if complete:
        ref = "pinnacle" if "pinnacle" in complete else min(complete, key=lambda b: overround(complete[b]))
        ref_prices = [next(q.price for q in s.quotes if q.bookmaker == ref) for s in mk.selections]
        fair = fair_probabilities(ref_prices)
        mk.margin = overround(ref_prices)
        mk.ref_book = ref
    else:
        med = [statistics.median(q.price for q in s.quotes) if s.quotes else 0 for s in mk.selections]
        fair = fair_probabilities(med) if all(m > 1 for m in med) else [s.raw_model_prob for s in mk.selections]
        mk.margin = None
        mk.ref_book = None

    pp = ctx.params
    mp = pp.market(mk.market)
    w = mp.model_weight
    out: list[Candidate] = []
    for s, f in zip(mk.selections, fair):
        s.fair_prob = f
        s.model_prob = w * s.raw_model_prob + (1 - w) * f
        hw = w * half_width(s.raw_model_prob) * mp.hw_scale + (1 - w) * 0.01
        s.prob_low, s.prob_high = max(0.005, s.model_prob - hw), min(0.995, s.model_prob + hw)
        fresh = [q for q in s.quotes if q.captured_at >= fresh_cut]
        best = max(fresh, key=lambda q: q.price) if fresh else None
        if best is None:
            continue
        ev = expected_value(s.model_prob, best.price)
        implied = implied_probability(best.price)
        snr = (s.model_prob - f) / max(hw, 1e-3)
        q = quality(snr, ctx.completeness, ev, ctx.lineups_confirmed, best.price, ctx.both_teams_known)
        out.append(Candidate(mk, s, best, ev, implied, q, risk(hw, best.price, ctx.completeness), hw))

    valid = [c for c in out if recommendable(c, ctx)]
    top = max(out, key=lambda c: c.ev) if out else None
    if not out:
        mk.verdict = "Brak aktualnych kursów dla tego rynku — nie wyceniono."
    elif not pp.can_recommend(mk.market) and top:
        mk.verdict = (
            f"Model w walidacji ({mp.reason or 'brak dowodu przewagi nad rynkiem w backteście'}) — bez rekomendacji. "
            f"Najlepsza selekcja: „{top.sel.label}”, EV {fmt_signed(top.ev)}."
        )
    elif valid:
        b = max(valid, key=lambda c: c.ev)
        mk.verdict = f"Dodatnie EV {fmt_signed(b.ev)} na „{b.sel.label}”."
    elif top and top.ev <= 0:
        mk.verdict = f"Najlepsza selekcja ({top.sel.label}) ma ujemne EV {fmt_signed(top.ev)} — kurs poniżej wartości godziwej."
    elif top and top.ev < pp.min_ev:
        mk.verdict = f"Przewaga {fmt_signed(top.ev)} na „{top.sel.label}” poniżej progu {fmt_pct(pp.min_ev, 0)} — mieści się w niepewności."
    elif top and abs(top.sel.raw_model_prob - top.sel.fair_prob) > pp.max_disagreement:
        mk.verdict = (
            f"„{top.sel.label}”: model ({fmt_pct(top.sel.raw_model_prob)}) i rynek ({fmt_pct(top.sel.fair_prob)}) różnią się zbyt mocno — "
            "prawdopodobnie modelowi brakuje informacji (kontuzje, skład). Bez rekomendacji."
        )
    elif top:
        mk.verdict = f"„{top.sel.label}”: EV {fmt_signed(top.ev)}, ale ocena jakości {top.quality} < {pp.min_quality} lub warunki niespełnione."
    return valid


def market_candidates(mk: Market, ctx: Context, medians: list[float | None] | None = None, min_books: int = MARKET_MIN_BOOKS) -> list[Candidate]:
    """"Tryb rynkowy": selections where some bookmaker pays at least MARKET_MIN_EV above the margin-free price of the
    reference (lowest-margin) book. Call after price_market (which sets fair_prob and ref_book).

    Guards: low-margin reference, enough books, best price not an outlier against the median (stale / wrong quotes),
    half-point lines only, price cap, kick-off more than 30 minutes away. `medians`: backtest substitute for quotes.
    """
    if mk.ref_book is None or mk.margin is None or mk.margin > MARKET_MAX_REF_MARGIN or ctx.kickoff - ctx.now <= timedelta(minutes=30):
        return []
    fresh_cut = ctx.now - timedelta(hours=MAX_ODDS_AGE_H)
    out: list[Candidate] = []
    for i, s in enumerate(mk.selections):
        if not (s.line is None or abs(s.line * 2) % 2 == 1) or s.fair_prob <= 0:
            continue
        others = [q for q in s.quotes if q.bookmaker != mk.ref_book and q.captured_at >= fresh_cut]
        if len(others) < min_books or not others:
            continue
        best = max(others, key=lambda q: q.price)
        med = medians[i] if medians is not None else statistics.median(q.price for q in s.quotes)
        if med is None or best.price > med * (1 + MARKET_MAX_OVER_MEDIAN) or best.price > MARKET_MAX_PRICE:
            continue
        ev = s.fair_prob * best.price - 1
        if ev < MARKET_MIN_EV:
            continue
        q = int(round(min(85, 55 + 400 * min(ev, 0.06) + min(8, len(s.quotes) / 3))))
        hw = 0.01
        out.append(Candidate(mk, s, best, ev, implied_probability(best.price), q, risk(hw, best.price, 0.8), hw, "market", len(s.quotes), med))
    return out


def recommendable(c: Candidate, ctx: Context) -> bool:
    half_point = c.sel.line is None or (abs(c.sel.line * 2) % 2 == 1)
    pp = ctx.params
    return (
        pp.can_recommend(c.market.market)
        and c.ev >= pp.min_ev
        and c.quality >= pp.min_quality
        and c.best.price <= MAX_PRICE
        and half_point
        and abs(c.sel.raw_model_prob - c.sel.fair_prob) <= pp.max_disagreement
        and ctx.both_teams_known
        and ctx.kickoff - ctx.now > timedelta(minutes=30)
    )


def quality(snr: float, completeness: float, ev: float, lineups_confirmed: bool, price: float, known: bool) -> int:
    q = 47 + 13 * max(-1.0, min(snr, 2.2)) + 13 * completeness + max(0.0, min(ev, 0.1)) * 80
    if not lineups_confirmed:
        q -= 2
    if price > 3:
        q -= 4
    if not known:
        q -= 20
    return int(round(max(0, min(97, q))))


def risk(hw: float, price: float, completeness: float) -> str:
    s = hw * 2 + (price - 1) * 0.06 + (1 - completeness) * 0.2
    return "low" if s < 0.22 else "high" if s > 0.33 else "medium"
