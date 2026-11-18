"""Walk-forward predictions of the live NBA ratings model on archived seasons (refit every day before games).

Training window: games before the refit time, at most ~1.5 seasons back (live: current + previous season).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..models.basketball import XI, Game, Ratings, half_width_n
from ..models.schedule import GameCtx, contexts
from .data import NbaGame

WINDOW = timedelta(days=550)
WARMUP = timedelta(days=150)


@dataclass
class NbaPred:
    g: NbaGame
    as_of: datetime
    margin: float
    total: float
    p_home: float
    p_cover: float | None  # home side covers the closing spread
    p_over: float | None  # over the closing total
    sigma_m: float
    sigma_t: float
    n_min: float
    known: bool
    ctx: GameCtx | None = None

    def half_width(self, p: float) -> float:
        return half_width_n(p, self.n_min)


def key(g: NbaGame) -> str:
    return f"{g.date:%Y%m%d}:{g.home}:{g.away}"


def walk_forward(games: list[NbaGame], xi: float = XI, fatigue: bool = False) -> list[NbaPred]:
    gs = sorted(games, key=lambda g: g.date)
    if len(gs) < 100:
        return []
    ctx = contexts([(key(g), g.date, g.home, g.away, g.home) for g in gs])
    out: list[NbaPred] = []
    days = sorted({g.date.date() for g in gs})
    first = gs[0].date + WARMUP
    lo = hi = 0
    for d in days:
        batch = [g for g in gs[hi:] if g.date.date() == d]
        if not batch:
            continue
        t = min(g.date for g in batch) - timedelta(hours=8)  # morning run before the games
        while hi < len(gs) and gs[hi].date < t:
            hi += 1
        while lo < hi and gs[lo].date < t - WINDOW:
            lo += 1
        if t < first or hi - lo < 100:
            continue
        model = Ratings.fit([Game(g.home, g.away, g.hp, g.ap, (t - g.date).total_seconds() / 86400, ctx[key(g)]) for g in gs[lo:hi]], xi=xi, fatigue=fatigue)
        for g in batch:
            c = ctx[key(g)]
            margin, total = model.predict(g.home, g.away, c)
            out.append(
                NbaPred(
                    g,
                    t,
                    margin,
                    total,
                    model.p_home_win(g.home, g.away, c),
                    model.p_home_cover(g.home, g.away, g.spread_home, c) if g.spread_home is not None else None,
                    model.p_over(g.home, g.away, g.total, c) if g.total is not None else None,
                    model.sigma_m,
                    model.sigma_t,
                    min(model.n_eff.get(g.home, 0.0), model.n_eff.get(g.away, 0.0)),
                    model.known(g.home) and model.known(g.away),
                    c,
                )
            )
    return out
