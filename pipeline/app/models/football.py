"""Dixon–Coles bivariate Poisson model with exponential time decay.

Maximum-likelihood fit per competition (analytic gradient). Uncertainty from effective sample size; its scale
is calibrated out of sample by the ETAP 5 backtest (calibration.json: hw_scale), together with the decay XI.
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
    def fit(cls, matches: list[Match], xi: float = XI, ridge: float = 0.02, init: "DixonColes | None" = None) -> "DixonColes":
        teams = sorted({m.home for m in matches} | {m.away for m in matches})
        if len(matches) < 10 or len(teams) < 3:
            return cls(teams=teams, att=np.zeros(len(teams)), dfn=np.zeros(len(teams)), n_matches=len(matches))
        idx = {t: i for i, t in enumerate(teams)}
        n = len(teams)
        nll, w = objective(matches, teams, xi, ridge)
        theta0 = np.concatenate([np.zeros(2 * n), [0.25, -0.05, 0.25]])
        if init is not None:
            # warm start (walk-forward refits): previous parameters for teams still present
            for t, i in idx.items():
                if t in init.teams:
                    j = init.teams.index(t)
                    theta0[i], theta0[n + i] = init.att[j], init.dfn[j]
            theta0[2 * n :] = [init.home_adv, init.rho, init.base]
        bounds = [(-3, 3)] * (2 * n) + [(-0.5, 1.0), (-0.3, 0.3), (-1.5, 1.5)]
        res = minimize(nll, theta0, method="L-BFGS-B", jac=True, bounds=bounds)
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
        return score_matrix(lam, mu, self.rho)

    def half_width(self, p: float, home: str, away: str) -> float:
        """Approximate half-width of the probability interval (scaled by hw_scale from calibration.json)."""
        return half_width_n(p, min(self.n_eff.get(home, 0.0), self.n_eff.get(away, 0.0)))

    def known(self, team: str) -> bool:
        return self.n_eff.get(team, 0.0) >= 3


def score_matrix(lam: float, mu: float, rho: float) -> np.ndarray:
    """P(home goals = i, away goals = j) with the Dixon–Coles low-score correction."""
    g = np.arange(MAX_GOALS + 1)
    ph = np.exp(g * math.log(lam) - lam - gammaln(g + 1))
    pa = np.exp(g * math.log(mu) - mu - gammaln(g + 1))
    m = np.outer(ph, pa)
    m[0, 0] *= 1 - lam * mu * rho
    m[0, 1] *= 1 + lam * rho
    m[1, 0] *= 1 + mu * rho
    m[1, 1] *= 1 - rho
    return m / m.sum()


def half_width_n(p: float, n: float) -> float:
    return min(0.25, math.sqrt(max(p * (1 - p), 1e-4)) * 0.9 / math.sqrt(n + 5))


def objective(matches: list[Match], teams: list[str], xi: float, ridge: float):
    """(nll(theta) -> (value, gradient), weights) for DixonColes.fit. theta = [att(n), dfn(n), home, rho, base]."""
    idx = {t: i for i, t in enumerate(teams)}
    h = np.array([idx[m.home] for m in matches])
    a = np.array([idx[m.away] for m in matches])
    x = np.array([m.hg for m in matches], dtype=float)
    y = np.array([m.ag for m in matches], dtype=float)
    w = np.exp(-xi * np.array([m.days_ago for m in matches]))
    n = len(teams)
    lgx, lgy = gammaln(x + 1), gammaln(y + 1)
    low = (x <= 1) & (y <= 1)

    def nll(theta: np.ndarray) -> tuple[float, np.ndarray]:
        """Negative weighted log-likelihood + penalties, with its analytic gradient (fast refits in backtests)."""
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
        tau_c = np.clip(tau, 1e-10, None)
        ll = ll + np.log(tau_c)
        penalty = 100.0 * (att.sum() ** 2 + dfn.sum() ** 2) + ridge * (att @ att + dfn @ dfn)
        # d(log tau)/d(log lam), d(log tau)/d(log mu), d(log tau)/d(rho)
        dl, dm, dr = np.zeros_like(lam), np.zeros_like(lam), np.zeros_like(lam)
        dl[m00] = dm[m00] = -lam[m00] * mu[m00] * rho / tau_c[m00]
        dr[m00] = -lam[m00] * mu[m00] / tau_c[m00]
        dl[m01] = lam[m01] * rho / tau_c[m01]
        dr[m01] = lam[m01] / tau_c[m01]
        dm[m10] = mu[m10] * rho / tau_c[m10]
        dr[m10] = mu[m10] / tau_c[m10]
        dr[m11] = -1 / tau_c[m11]
        gl = w * (x - lam + dl)  # d ll / d log(lam)
        gm = w * (y - mu + dm)  # d ll / d log(mu)
        g_att = np.bincount(h, gl, n) + np.bincount(a, gm, n)
        g_dfn = np.bincount(a, gl, n) + np.bincount(h, gm, n)
        grad = -np.concatenate([g_att, g_dfn, [gl.sum(), (w * dr).sum(), gl.sum() + gm.sum()]])
        grad[:n] += 200.0 * att.sum() + 2 * ridge * att
        grad[n : 2 * n] += 200.0 * dfn.sum() + 2 * ridge * dfn
        return float(-(w * ll).sum() + penalty), grad

    return nll, w


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
