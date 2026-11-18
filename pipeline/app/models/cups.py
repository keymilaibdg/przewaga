"""Cross-league ratings for the UEFA cups (Champions League, Europa League).

One Poisson model with the Dixon–Coles low-score correction is fitted jointly on many domestic leagues
(football-data.co.uk) and on UEFA cup matches. Team strengths of different leagues become comparable only
through the cup matches, which link the leagues. Home advantage is estimated per competition (domestic leagues
differ; neutral finals have none).

The weekly job `python -m app.backtest ratings` writes app/cup_ratings.json; the daily pipeline maps the cup teams
of its database to those ratings (cup_model) and uses them like a league model.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

from ..matching import similarity
from .football import DixonColes

RATINGS_PATH = Path(__file__).resolve().parents[1] / "cup_ratings.json"
XI = 0.0019
MIN_SIM = 0.85

# football-data.co.uk file -> country code used in team keys
FD_COUNTRY = {
    "E0": "ENG", "E1": "ENG", "SC0": "SCO", "D1": "GER", "I1": "ITA", "SP1": "ESP", "F1": "FRA", "N1": "NED", "B1": "BEL",
    "P1": "POR", "T1": "TUR", "G1": "GRE", "AUT": "AUT", "DNK": "DEN", "NOR": "NOR", "SWE": "SWE", "SWZ": "SUI", "POL": "POL",
    "ROU": "ROU", "IRL": "IRL", "FIN": "FIN",
}
# API-Football country names -> the same codes
AF_COUNTRY = {
    "England": "ENG", "Scotland": "SCO", "Germany": "GER", "Italy": "ITA", "Spain": "ESP", "France": "FRA", "Netherlands": "NED",
    "Belgium": "BEL", "Portugal": "POR", "Turkey": "TUR", "Türkiye": "TUR", "Greece": "GRE", "Austria": "AUT", "Denmark": "DEN",
    "Norway": "NOR", "Sweden": "SWE", "Switzerland": "SUI", "Poland": "POL", "Romania": "ROU", "Ireland": "IRL", "Finland": "FIN",
}
# Our domestic leagues -> country code (live mapping of database teams through their CSV names)
LEAGUE_COUNTRY = {"epl": "ENG", "laliga": "ESP", "bundesliga": "GER", "ekstraklasa": "POL"}


@dataclass
class GMatch:
    home: str
    away: str
    hg: int
    ag: int
    days_ago: float
    group: str  # competition: domestic file code ('E0') or 'cup'; 'neutral' = no home advantage


def fit(matches: list[GMatch], xi: float = XI, ridge: float = 0.05) -> dict:
    """Joint fit. Returns a JSON-able dict (teams with att/dfn/n_eff, home advantage per group, base, rho)."""
    teams = sorted({m.home for m in matches} | {m.away for m in matches})
    groups = sorted({m.group for m in matches if m.group != "neutral"})
    ti = {t: i for i, t in enumerate(teams)}
    gi = {g: i for i, g in enumerate(groups)}
    n, G = len(teams), len(groups)
    h = np.array([ti[m.home] for m in matches])
    a = np.array([ti[m.away] for m in matches])
    gidx = np.array([gi.get(m.group, 0) for m in matches])
    has_home = np.array([m.group != "neutral" for m in matches], dtype=float)
    x = np.array([m.hg for m in matches], dtype=float)
    y = np.array([m.ag for m in matches], dtype=float)
    w = np.exp(-xi * np.array([m.days_ago for m in matches]))
    lgx, lgy = gammaln(x + 1), gammaln(y + 1)
    m00 = (x == 0) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m10 = (x == 1) & (y == 0)
    m11 = (x == 1) & (y == 1)

    def nll(theta: np.ndarray) -> tuple[float, np.ndarray]:
        att, dfn, home, rho, base = theta[:n], theta[n : 2 * n], theta[2 * n : 2 * n + G], theta[2 * n + G], theta[2 * n + G + 1]
        lam = np.exp(base + att[h] + dfn[a] + home[gidx] * has_home)
        mu = np.exp(base + att[a] + dfn[h])
        tau = np.ones_like(lam)
        tau[m00] = 1 - lam[m00] * mu[m00] * rho
        tau[m01] = 1 + lam[m01] * rho
        tau[m10] = 1 + mu[m10] * rho
        tau[m11] = 1 - rho
        tc = np.clip(tau, 1e-10, None)
        ll = x * np.log(lam) - lam - lgx + y * np.log(mu) - mu - lgy + np.log(tc)
        dl, dm, dr = np.zeros_like(lam), np.zeros_like(lam), np.zeros_like(lam)
        dl[m00] = dm[m00] = -lam[m00] * mu[m00] * rho / tc[m00]
        dr[m00] = -lam[m00] * mu[m00] / tc[m00]
        dl[m01] = lam[m01] * rho / tc[m01]
        dr[m01] = lam[m01] / tc[m01]
        dm[m10] = mu[m10] * rho / tc[m10]
        dr[m10] = mu[m10] / tc[m10]
        dr[m11] = -1 / tc[m11]
        gl, gm = w * (x - lam + dl), w * (y - mu + dm)
        g = np.zeros_like(theta)
        g[:n] = -(np.bincount(h, gl, n) + np.bincount(a, gm, n))
        g[n : 2 * n] = -(np.bincount(a, gl, n) + np.bincount(h, gm, n))
        g[2 * n : 2 * n + G] = -np.bincount(gidx, gl * has_home, G)
        g[2 * n + G] = -(w * dr).sum()
        g[2 * n + G + 1] = -(gl.sum() + gm.sum())
        pen = 100.0 * (att.sum() ** 2 + dfn.sum() ** 2) + ridge * (att @ att + dfn @ dfn)
        g[:n] += 200.0 * att.sum() + 2 * ridge * att
        g[n : 2 * n] += 200.0 * dfn.sum() + 2 * ridge * dfn
        return float(-(w * ll).sum() + pen), g

    theta0 = np.concatenate([np.zeros(2 * n), np.full(G, 0.25), [-0.05, 0.25]])
    bounds = [(-3, 3)] * (2 * n) + [(-0.5, 1.0)] * G + [(-0.3, 0.3), (-1.5, 1.5)]
    th = minimize(nll, theta0, method="L-BFGS-B", jac=True, bounds=bounds, options={"maxiter": 3000}).x
    n_eff = np.bincount(h, w, n) + np.bincount(a, w, n)
    cup = np.array([m.group in ("cup", "neutral") for m in matches], dtype=float)
    n_cup = np.bincount(h, w * cup, n) + np.bincount(a, w * cup, n)
    home = {g: float(th[2 * n + i]) for g, i in gi.items()}
    return {
        "xi": xi,
        "base": float(th[2 * n + G + 1]),
        "rho": float(th[2 * n + G]),
        "home": home,
        "cup_home": home.get("cup", 0.25),
        "teams": {t: {"att": float(th[i]), "dfn": float(th[n + i]), "n_eff": float(n_eff[i]), "n_cup": float(n_cup[i])} for t, i in ti.items()},
    }


def rates(r: dict, home: str, away: str, neutral: bool = False) -> tuple[float, float] | None:
    th, ta = r["teams"].get(home), r["teams"].get(away)
    if th is None or ta is None:
        return None
    lam = math.exp(r["base"] + th["att"] + ta["dfn"] + (0 if neutral else r["cup_home"]))
    mu = math.exp(r["base"] + ta["att"] + th["dfn"])
    return lam, mu


# ---------------- name -> rating key ----------------


def find_key(name: str, entries: dict[str, dict], country: str | None = None) -> str | None:
    """Rating key for a team name: best unique similar name (all names a team is known by), within a country if given."""
    scores: dict[str, float] = {}
    for key, e in entries.items():
        if country and not key.startswith(country + ":"):
            continue
        names = [e.get("name") or key.split(":", 1)[1], *e.get("aliases", [])]
        scores[key] = max(similarity(name, nm) for nm in names)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] < MIN_SIM or (len(ranked) > 1 and ranked[1][1] >= ranked[0][1]):
        return None
    return ranked[0][0]


# ---------------- live use ----------------


def load(path: Path | str | None = None) -> dict | None:
    env = os.environ.get("PRZEWAGA_CUP_RATINGS")
    if path is None:
        if env is not None and env.strip().lower() in ("", "none"):
            return None
        path = Path(env) if env else RATINGS_PATH
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def team_key(conn: sqlite3.Connection, team_id: str, name: str, r: dict) -> str | None:
    """Our database team -> rating key. Teams of our domestic leagues go through their CSV name (exact)."""
    rows = conn.execute("SELECT league_key, name FROM team_aliases WHERE team_id = ? AND source = 'csv'", (team_id,)).fetchall()
    for row in rows:
        cc = LEAGUE_COUNTRY.get(row["league_key"])
        if cc and f"{cc}:{row['name']}" in r["teams"]:
            return f"{cc}:{row['name']}"
    names = {name} | {row["name"] for row in conn.execute("SELECT name FROM team_aliases WHERE team_id = ?", (team_id,))}
    for nm in names:
        k = find_key(nm, r["teams"])
        if k:
            return k
    return None


def cup_model(conn: sqlite3.Connection, league_key: str, now: datetime, ratings: dict | None = None) -> DixonColes | None:
    """DixonColes-compatible model for the cup teams of `league_key`, from the cross-league ratings."""
    r = ratings if ratings is not None else load()
    if not r:
        return None
    rows = conn.execute(
        """SELECT DISTINCT t.id, t.name FROM teams t JOIN events e ON t.id IN (e.home_team_id, e.away_team_id)
           WHERE e.league_key = ?""",
        (league_key,),
    ).fetchall()
    ids, att, dfn, n_eff = [], [], [], {}
    for row in rows:
        k = team_key(conn, row["id"], row["name"], r)
        if k is None:
            continue
        e = r["teams"][k]
        ids.append(row["id"])
        att.append(e["att"])
        dfn.append(e["dfn"])
        # a team known only from a handful of cup games is not 'known' (no domestic league in the free data)
        n_eff[row["id"]] = e["n_eff"] if e["n_eff"] - e["n_cup"] >= 5 or e["n_cup"] >= 12 else min(e["n_eff"], 2.0)
    if not ids:
        return None
    return DixonColes(teams=ids, att=np.array(att), dfn=np.array(dfn), home_adv=r["cup_home"], base=r["base"], rho=r["rho"], n_eff=n_eff, n_matches=len(ids))
