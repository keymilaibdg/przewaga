"""Basketball ratings model: time-weighted ridge regression on margins and on team points.

margin   = hca + r_home - r_away + e,         e ~ N(0, sigma_m^2)
points_h = base + off_home - def_away + hca/2 ; points_a = base + off_away - def_home - hca/2
total    = points_h + points_a,               residual ~ N(0, sigma_t^2)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm

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

    @classmethod
    def fit(cls, games: list[Game], xi: float = XI, ridge: float = 3.0) -> "Ratings":
        teams = sorted({g.home for g in games} | {g.away for g in games})
        if len(games) < 15 or len(teams) < 3:
            base = float(np.mean([(g.hp + g.ap) / 2 for g in games])) if games else 110.0
            return cls(teams=teams, base=base, n_games=len(games))
        idx = {t: i for i, t in enumerate(teams)}
        n, k = len(teams), len(games)
        w = np.exp(-xi * np.array([g.days_ago for g in games]))

        # margins
        X = np.zeros((k, n + 1))
        X[:, 0] = 1.0
        for r, g in enumerate(games):
            X[r, 1 + idx[g.home]] = 1.0
            X[r, 1 + idx[g.away]] = -1.0
        yv = np.array([g.hp - g.ap for g in games], dtype=float)
        R = np.diag([0.0] + [ridge] * n)
        beta = np.linalg.solve((X * w[:, None]).T @ X + R, (X * w[:, None]).T @ yv)
        resid = yv - X @ beta
        sigma_m = float(np.sqrt((w * resid**2).sum() / w.sum()))

        # team points (two rows per game)
        P = np.zeros((2 * k, 1 + 2 * n + 1))
        pts = np.zeros(2 * k)
        for r, g in enumerate(games):
            hi, ai = idx[g.home], idx[g.away]
            P[2 * r, 0] = 1.0
            P[2 * r, 1 + hi] = 1.0  # off home
            P[2 * r, 1 + n + ai] = -1.0  # def away
            P[2 * r, -1] = 0.5
            pts[2 * r] = g.hp
            P[2 * r + 1, 0] = 1.0
            P[2 * r + 1, 1 + ai] = 1.0
            P[2 * r + 1, 1 + n + hi] = -1.0
            P[2 * r + 1, -1] = -0.5
            pts[2 * r + 1] = g.ap
        w2 = np.repeat(w, 2)
        R2 = np.diag([0.0] + [ridge] * (2 * n) + [0.0])
        gamma = np.linalg.solve((P * w2[:, None]).T @ P + R2, (P * w2[:, None]).T @ pts)
        tot_pred = np.array([2 * gamma[0] + gamma[1 + idx[g.home]] + gamma[1 + idx[g.away]] - gamma[1 + n + idx[g.away]] - gamma[1 + n + idx[g.home]] for g in games])
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
        )

    def predict(self, home: str, away: str) -> tuple[float, float]:
        """(expected home margin, expected total points)."""
        margin = self.hca + self.rating.get(home, 0.0) - self.rating.get(away, 0.0)
        total = 2 * self.base + self.off.get(home, 0.0) + self.off.get(away, 0.0) - self.dfn.get(home, 0.0) - self.dfn.get(away, 0.0)
        return margin, total

    def p_home_win(self, home: str, away: str) -> float:
        m, _ = self.predict(home, away)
        return float(1 - norm.cdf(0, loc=m, scale=self.sigma_m))

    def p_home_cover(self, home: str, away: str, point: float) -> float:
        """P(margin + point > 0) for the home side's handicap `point` (e.g. -5.5)."""
        m, _ = self.predict(home, away)
        return float(1 - norm.cdf(-point, loc=m, scale=self.sigma_m))

    def p_over(self, home: str, away: str, line: float) -> float:
        _, t = self.predict(home, away)
        return float(1 - norm.cdf(line, loc=t, scale=self.sigma_t))

    def half_width(self, p: float, home: str, away: str) -> float:
        return half_width_n(p, min(self.n_eff.get(home, 0.0), self.n_eff.get(away, 0.0)))

    def known(self, team: str) -> bool:
        return self.n_eff.get(team, 0.0) >= 3
