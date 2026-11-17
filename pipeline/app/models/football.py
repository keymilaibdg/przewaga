"""Dixon–Coles bivariate Poisson model with exponential time decay.

v0: maximum-likelihood fit per competition; uncertainty from effective sample size.
Stage 5 replaces the uncertainty approximation with a parametric bootstrap and calibrates it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

MAX_GOALS = 10
XI = 0.0019  # per-day decay => half-life ~ 1 year


@dataclass
class Match:
    home: str
    away: str
    hg: int
    ag: int
    days_ago: float


@dataclass
class DixonColes:
    teams: list[str] = field(default_factory=list)
    att: np.ndarray = field(default_factory=lambda: np.zeros(0))
    dfn: np.ndarray = field(default_factory=lambda: np.zeros(0))
    home_adv: float = 0.25
    base: float = 0.25
    rho: float = -0.05
    n_eff: dict[str, float] = field(default_factory=dict)
    n_matches: int = 0

    # ---------- fitting ----------
    @classmethod
    def fit(cls, matches: list[Match], xi: float = XI, ridge: float = 0.02) -> "DixonColes":
        teams = sorted({m.home for m in matches} | {m.away for m in matches})
        if len(matches) < 10 or len(teams) < 3:
            return cls(teams=teams, att=np.zeros(len(teams)), dfn=np.zeros(len(teams)), n_matches=len(matches))
        idx = {t: i for i, t in enumerate(teams)}
        h = np.array([idx[m.home] for m in matches])
        a = np.array([idx[m.away] for m in matches])
        x = np.array([m.hg for m in matches], dtype=float)
        y = np.array([m.ag for m in matches], dtype=float)
        w = np.exp(-xi * np.array([m.days_ago for m in matches]))
        n = len(teams)
        lgx, lgy = gammaln(x + 1), gammaln(y + 1)
        low = (x <= 1) & (y <= 1)

        def nll(theta: np.ndarray) -> float:
            att, dfn, home, rho, base = theta[:n], theta[n : 2 * n], theta[2 * n], theta[2 * n + 1], theta[2 * n + 2]
            lam = np.exp(base + att[h] + dfn[a] + home)
            mu = np.exp(base + att[a] + dfn[h])
            ll = x * np.log(lam) - lam - lgx + y * np.log(mu) - mu - lgy
            tau = np.ones_like(lam)
            m00 = low & (x == 0) & (y == 0)
            m01 = low & (x == 0) & (y == 1)
            m10 = low & (x == 1) & (y == 0)
            m11 = low & (x == 1) & (y == 1)
            tau[m00] = 1 - lam[m00] * mu[m00] * rho
            tau[m01] = 1 + lam[m01] * rho
            tau[m10] = 1 + mu[m10] * rho
            tau[m11] = 1 - rho
            ll = ll + np.log(np.clip(tau, 1e-10, None))
            penalty = 100.0 * (att.sum() ** 2 + dfn.sum() ** 2) + ridge * (att @ att + dfn @ dfn)
            return float(-(w * ll).sum() + penalty)

        theta0 = np.concatenate([np.zeros(2 * n), [0.25, -0.05, 0.25]])
        bounds = [(-3, 3)] * (2 * n) + [(-0.5, 1.0), (-0.3, 0.3), (-1.5, 1.5)]
        res = minimize(nll, theta0, method="L-BFGS-B", bounds=bounds)
        th = res.x
        n_eff: dict[str, float] = {}
        for m, wi in zip(matches, w):
            n_eff[m.home] = n_eff.get(m.home, 0.0) + wi
            n_eff[m.away] = n_eff.get(m.away, 0.0) + wi
        return cls(teams=teams, att=th[:n], dfn=th[n : 2 * n], home_adv=float(th[2 * n]), rho=float(th[2 * n + 1]), base=float(th[2 * n + 2]), n_eff=n_eff, n_matches=len(matches))

    # ---------- prediction ----------
    def rates(self, home: str, away: str, neutral: bool = False) -> tuple[float, float]:
        idx = {t: i for i, t in enumerate(self.teams)}
        ah, dh = (self.att[idx[home]], self.dfn[idx[home]]) if home in idx else (0.0, 0.0)
        aa, da = (self.att[idx[away]], self.dfn[idx[away]]) if away in idx else (0.0, 0.0)
        base = self._base()
        lam = math.exp(base + ah + da + (0 if neutral else self.home_adv))
        mu = math.exp(base + aa + dh)
        return lam, mu

    def _base(self) -> float:
        return self.base

    def score_matrix(self, home: str, away: str) -> np.ndarray:
        lam, mu = self.rates(home, away)
        g = np.arange(MAX_GOALS + 1)
        ph = np.exp(g * math.log(lam) - lam - gammaln(g + 1))
        pa = np.exp(g * math.log(mu) - mu - gammaln(g + 1))
        m = np.outer(ph, pa)
        m[0, 0] *= 1 - lam * mu * self.rho
        m[0, 1] *= 1 + lam * self.rho
        m[1, 0] *= 1 + mu * self.rho
        m[1, 1] *= 1 - self.rho
        return m / m.sum()

    def half_width(self, p: float, home: str, away: str) -> float:
        """Approximate half-width of the probability interval (v0)."""
        n = min(self.n_eff.get(home, 0.0), self.n_eff.get(away, 0.0))
        return min(0.25, math.sqrt(max(p * (1 - p), 1e-4)) * 0.9 / math.sqrt(n + 5))

    def known(self, team: str) -> bool:
        return self.n_eff.get(team, 0.0) >= 3


def outcome_probs(m: np.ndarray) -> dict[str, float]:
    i, j = np.indices(m.shape)
    return {"home": float(m[i > j].sum()), "draw": float(m[i == j].sum()), "away": float(m[i < j].sum())}


def total_over(m: np.ndarray, line: float) -> float:
    i, j = np.indices(m.shape)
    return float(m[(i + j) > line].sum())


def handicap_home(m: np.ndarray, point: float) -> float:
    """P(home goals + point > away goals) for half-point lines."""
    i, j = np.indices(m.shape)
    return float(m[(i - j + point) > 0].sum())
