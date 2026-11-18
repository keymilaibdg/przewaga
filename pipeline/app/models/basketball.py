"""Basketball ratings model: time-weighted ridge regression on margins and on team points.

margin   = hca + r_home - r_away + b . f(schedule) + e,      e ~ N(0, sigma_m^2)
points_h = base + off_home - def_away + hca/2 + c . g_h ;  points_a = base + off_away - def_home - hca/2 + c . g_a
total    = points_h + points_a,                             residual ~ N(0, sigma_t^2)

f(schedule) (optional, `fatigue=True`): rest-day difference, home back-to-back, away back-to-back, travel difference
(models/schedule.py). g: own back-to-back, opponent back-to-back. Used only when the backtest says it helps.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm

from .schedule import GameCtx

XI = 0.008  # per-day decay => half-life ~ 3 months (basketball form moves faster)


def half_width_n(p: float, n: float) -> float:
    return min(0.25, math.sqrt(max(p * (1 - p), 1e-4)) * 1.1 / math.sqrt(n + 5))


@dataclass
class Game:
    home: str
    away: str
    hp: int
    ap: int
    days_ago: float
    ctx: GameCtx | None = None


FATIGUE_NAMES = ("rest_diff", "b2b_home", "b2b_away", "travel_1000km")


@dataclass
class Ratings:
    teams: list[str] = field(default_factory=list)
    rating: dict[str, float] = field(default_factory=dict)
    off: dict[str, float] = field(default_factory=dict)
    dfn: dict[str, float] = field(default_factory=dict)
    hca: float = 2.5
    base: float = 110.0
    sigma_m: float = 12.5
    sigma_t: float = 18.0
    n_eff: dict[str, float] = field(default_factory=dict)
    n_games: int = 0
    fatigue: dict[str, float] = field(default_factory=dict)  # margin coefficients (points), empty = not used
    fatigue_pts: tuple[float, float] = (0.0, 0.0)  # team points: own back-to-back, opponent back-to-back

    @classmethod
    def fit(cls, games: list[Game], xi: float = XI, ridge: float = 3.0, fatigue: bool = False) -> "Ratings":
        teams = sorted({g.home for g in games} | {g.away for g in games})
        if len(games) < 15 or len(teams) < 3:
            base = float(np.mean([(g.hp + g.ap) / 2 for g in games])) if games else 110.0
            return cls(teams=teams, base=base, n_games=len(games))
        idx = {t: i for i, t in enumerate(teams)}
        n, k = len(teams), len(games)
        w = np.exp(-xi * np.array([g.days_ago for g in games]))

        nf = len(FATIGUE_NAMES) if fatigue else 0
        # margins
        X = np.zeros((k, n + 1 + nf))
        X[:, 0] = 1.0
        for r, g in enumerate(games):
            X[r, 1 + idx[g.home]] = 1.0
            X[r, 1 + idx[g.away]] = -1.0
            if nf and g.ctx is not None:
                X[r, n + 1 :] = g.ctx.features()
        yv = np.array([g.hp - g.ap for g in games], dtype=float)
        R = np.diag([0.0] + [ridge] * n + [0.5] * nf)
        beta = np.linalg.solve((X * w[:, None]).T @ X + R, (X * w[:, None]).T @ yv)
        resid = yv - X @ beta
        sigma_m = float(np.sqrt((w * resid**2).sum() / w.sum()))

        # team points (two rows per game); last columns: hca share, [own b2b, opponent b2b]
        npf = 2 if fatigue else 0
        hc = 1 + 2 * n  # hca column
        P = np.zeros((2 * k, 1 + 2 * n + 1 + npf))
        pts = np.zeros(2 * k)
        for r, g in enumerate(games):
            hi, ai = idx[g.home], idx[g.away]
            bh = float(g.ctx.home.b2b) if g.ctx else 0.0
            ba = float(g.ctx.away.b2b) if g.ctx else 0.0
            P[2 * r, 0] = 1.0
            P[2 * r, 1 + hi] = 1.0  # off home
            P[2 * r, 1 + n + ai] = -1.0  # def away
            P[2 * r, hc] = 0.5
            pts[2 * r] = g.hp
            P[2 * r + 1, 0] = 1.0
            P[2 * r + 1, 1 + ai] = 1.0
            P[2 * r + 1, 1 + n + hi] = -1.0
            P[2 * r + 1, hc] = -0.5
            pts[2 * r + 1] = g.ap
            if npf:
                P[2 * r, hc + 1 :] = (bh, ba)
                P[2 * r + 1, hc + 1 :] = (ba, bh)
        w2 = np.repeat(w, 2)
        R2 = np.diag([0.0] + [ridge] * (2 * n) + [0.0] + [0.5] * npf)
        gamma = np.linalg.solve((P * w2[:, None]).T @ P + R2, (P * w2[:, None]).T @ pts)
        tot_pred = P[0::2] @ gamma + P[1::2] @ gamma
        tot_res = np.array([g.hp + g.ap for g in games]) - tot_pred
        sigma_t = float(np.sqrt((w * tot_res**2).sum() / w.sum()))

        n_eff: dict[str, float] = {}
        for g, wi in zip(games, w):
            n_eff[g.home] = n_eff.get(g.home, 0.0) + wi
            n_eff[g.away] = n_eff.get(g.away, 0.0) + wi
        return cls(
            teams=teams,
            rating={t: float(beta[1 + i]) for t, i in idx.items()},
            off={t: float(gamma[1 + i]) for t, i in idx.items()},
            dfn={t: float(gamma[1 + n + i]) for t, i in idx.items()},
            hca=float(beta[0]),
            base=float(gamma[0]),
            sigma_m=max(sigma_m, 6.0),
            sigma_t=max(sigma_t, 8.0),
            n_eff=n_eff,
            n_games=k,
            fatigue={nm: float(beta[n + 1 + i]) for i, nm in enumerate(FATIGUE_NAMES)} if nf else {},
            fatigue_pts=(float(gamma[hc + 1]), float(gamma[hc + 2])) if npf else (0.0, 0.0),
        )

    def schedule_effect(self, ctx: GameCtx | None) -> tuple[float, float]:
        """(margin points, total points) added by the schedule context (0 when the model does not use it)."""
        if ctx is None or not self.fatigue:
            return 0.0, 0.0
        f = ctx.features()
        margin = sum(self.fatigue[nm] * v for nm, v in zip(FATIGUE_NAMES, f))
        own, opp = self.fatigue_pts
        total = (own + opp) * (float(ctx.home.b2b) + float(ctx.away.b2b))
        return margin, total

    def predict(self, home: str, away: str, ctx: GameCtx | None = None) -> tuple[float, float]:
        """(expected home margin, expected total points)."""
        dm, dt = self.schedule_effect(ctx)
        margin = self.hca + self.rating.get(home, 0.0) - self.rating.get(away, 0.0) + dm
        total = 2 * self.base + self.off.get(home, 0.0) + self.off.get(away, 0.0) - self.dfn.get(home, 0.0) - self.dfn.get(away, 0.0) + dt
        return margin, total

    def p_home_win(self, home: str, away: str, ctx: GameCtx | None = None) -> float:
        m, _ = self.predict(home, away, ctx)
        return float(1 - norm.cdf(0, loc=m, scale=self.sigma_m))

    def p_home_cover(self, home: str, away: str, point: float, ctx: GameCtx | None = None) -> float:
        """P(margin + point > 0) for the home side's handicap `point` (e.g. -5.5)."""
        m, _ = self.predict(home, away, ctx)
        return float(1 - norm.cdf(-point, loc=m, scale=self.sigma_m))

    def p_over(self, home: str, away: str, line: float, ctx: GameCtx | None = None) -> float:
        _, t = self.predict(home, away, ctx)
        return float(1 - norm.cdf(line, loc=t, scale=self.sigma_t))

    def half_width(self, p: float, home: str, away: str) -> float:
        return half_width_n(p, min(self.n_eff.get(home, 0.0), self.n_eff.get(away, 0.0)))

    def known(self, team: str) -> bool:
        return self.n_eff.get(team, 0.0) >= 3
