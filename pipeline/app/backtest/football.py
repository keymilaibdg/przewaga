"""Walk-forward predictions of the live football model (Dixon–Coles) on historical seasons.

At every refit time T (weekly, Monday 06:00 UTC, like a morning run) the model is fitted only on matches that
kicked off before T (window: two years, like the live 'current + previous season'), and predicts the matches of
the following 7 days. Nothing after T is used: no data leakage.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..models.football import XI, DixonColes, Match, half_width_n, outcome_probs, total_over
from .data import FbMatch

WINDOW = timedelta(days=730)
STEP = timedelta(days=7)
WARMUP = timedelta(days=240)  # first predictions after ~8 months of history


@dataclass
class FbPred:
    m: FbMatch
    as_of: datetime
    p: tuple[float, float, float]  # home, draw, away
    p_over: float  # over 2.5 goals
    lam: float
    mu: float
    n_min: float  # min effective number of matches of the two teams (uncertainty, data completeness)
    known: bool

    def half_width(self, p: float) -> float:
        return half_width_n(p, self.n_min)


def _monday(d: datetime) -> datetime:
    d = d.astimezone(timezone.utc).replace(hour=6, minute=0, second=0, microsecond=0)
    return d - timedelta(days=d.weekday())


def walk_forward(matches: list[FbMatch], xi: float = XI) -> list[FbPred]:
    ms = sorted(matches, key=lambda m: m.kickoff)
    if len(ms) < 50:
        return []
    out: list[FbPred] = []
    t = _monday(ms[0].kickoff + WARMUP)
    end = ms[-1].kickoff
    model: DixonColes | None = None
    lo = 0  # first match inside the training window
    hi = 0  # first match at/after T
    while t <= end:
        while hi < len(ms) and ms[hi].kickoff < t:
            hi += 1
        while lo < hi and ms[lo].kickoff < t - WINDOW:
            lo += 1
        upcoming = [m for m in ms[hi:] if m.kickoff < t + STEP]
        if upcoming and hi - lo >= 50:
            train = [Match(m.home, m.away, m.hg, m.ag, (t - m.kickoff).total_seconds() / 86400) for m in ms[lo:hi]]
            model = DixonColes.fit(train, xi=xi, init=model)
            for m in upcoming:
                mat = model.score_matrix(m.home, m.away)
                o = outcome_probs(mat)
                lam, mu = model.rates(m.home, m.away)
                n_min = min(model.n_eff.get(m.home, 0.0), model.n_eff.get(m.away, 0.0))
                out.append(FbPred(m, t, (o["home"], o["draw"], o["away"]), total_over(mat, 2.5), lam, mu, n_min, model.known(m.home) and model.known(m.away)))
        t += STEP
    return out
