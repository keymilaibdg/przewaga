"""Offline fake of API-Football, API-Basketball and The Odds API with realistic response shapes.

A small synthetic world: one football league (Premier League) and NBA, previous + current season,
results generated from known team strengths, odds that sometimes misprice so the engine has something to find.
"""
from __future__ import annotations

import math
import random
import urllib.parse
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.providers.http import HttpResponse

FB_TEAMS = [
    (33, "Manchester United", 1.15, 0.95), (40, "Liverpool", 1.45, 0.80), (42, "Arsenal", 1.40, 0.75),
    (49, "Chelsea", 1.20, 0.90), (50, "Manchester City", 1.45, 0.80), (47, "Tottenham", 1.15, 1.05),
    (34, "Newcastle", 1.10, 0.95), (66, "Aston Villa", 1.10, 1.00), (51, "Brighton", 1.05, 1.05),
    (48, "West Ham", 0.95, 1.15),
]
# Odds API spells some names differently — the matcher must cope.
ODDS_NAMES = {"Tottenham": "Tottenham Hotspur", "Newcastle": "Newcastle United", "Brighton": "Brighton and Hove Albion", "West Ham": "West Ham United"}
BB_TEAMS = [(132, "Boston Celtics", 7.0), (145, "Los Angeles Lakers", 1.0), (139, "Denver Nuggets", 4.0), (149, "Milwaukee Bucks", 1.5), (141, "Golden State Warriors", 0.5), (152, "New York Knicks", 3.5)]


def _iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%S+00:00")


@dataclass
class FakeWorld:
    now: datetime
    seed: int = 7
    fail_next: dict[str, int] = field(default_factory=dict)  # endpoint substring -> number of 429s to return
    odds_skew: float = 0.06  # how much the fake market disagrees with the true model
    calls: list[str] = field(default_factory=list)
    odds_remaining: int = 500

    def __post_init__(self) -> None:
        rng = random.Random(self.seed)
        self.fixtures: list[dict] = []
        fid = 1000
        for season, start in (("2025", datetime(2025, 8, 15, tzinfo=timezone.utc)), ("2026", self.now - timedelta(days=35))):
            day = start
            pairs = [(h, a) for h in FB_TEAMS for a in FB_TEAMS if h != a]
            rng.shuffle(pairs)
            for i, (h, a) in enumerate(pairs):
                ko = day + timedelta(days=(i // 5) * 3.5, hours=15 + (i % 3) * 2)
                lam = 1.35 * h[2] * a[3] * 1.15
                mu = 1.35 * a[2] * h[3]
                fid += 1
                hg, ag = self._pois(rng, lam), self._pois(rng, mu)
                self.fixtures.append({"season": season, "id": fid, "ko": ko, "h": h, "a": a, "_hg": hg, "_ag": ag, "lam": lam, "mu": mu})
        self.games: list[dict] = []
        gid = 5000
        for season, start in (("2025-2026", datetime(2025, 10, 21, tzinfo=timezone.utc)), ("2026-2027", datetime(2026, 10, 20, tzinfo=timezone.utc))):
            for k in range(160):
                h, a = rng.sample(BB_TEAMS, 2)
                ko = start + timedelta(hours=12 * k + 1)
                gid += 1
                m = 2.5 + h[2] - a[2]
                margin = rng.gauss(m, 12)
                tot = rng.gauss(226, 16)
                hp, ap = int(round((tot + margin) / 2)), int(round((tot - margin) / 2))
                if hp == ap:
                    hp += 1
                self.games.append({"season": season, "id": gid, "ko": ko, "h": h, "a": a, "_hp": hp, "_ap": ap, "m": m})

    def played(self, x: dict) -> bool:
        return x["ko"] + timedelta(hours=2.5) < self.now

    def score(self, x: dict) -> tuple[int | None, int | None]:
        if not self.played(x):
            return None, None
        return (x["_hg"], x["_ag"]) if "_hg" in x else (x["_hp"], x["_ap"])

    @staticmethod
    def _pois(rng: random.Random, lam: float) -> int:
        l, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= rng.random()
            if p <= l:
                return k
            k += 1

    # ---- transport ----
    def get(self, url: str, headers: dict[str, str]) -> HttpResponse:
        u = urllib.parse.urlparse(url)
        q = dict(urllib.parse.parse_qsl(u.query))
        path = u.path
        self.calls.append(f"{u.netloc}{path}")
        for key in list(self.fail_next):
            if key in path and self.fail_next[key] > 0:
                self.fail_next[key] -= 1
                return HttpResponse(429, {}, {"message": "Too many requests"})
        if "football.api-sports.io" in u.netloc:
            if headers.get("x-apisports-key") != "test-key":
                return HttpResponse(200, {}, {"errors": {"token": "Error/Missing application key."}, "response": []})
            return self._football(path, q)
        if "basketball.api-sports.io" in u.netloc:
            return self._basketball(path, q)
        if "the-odds-api.com" in u.netloc:
            return self._odds(path, q)
        return HttpResponse(404, {}, {"message": "not found"})

    def _hdr(self) -> dict[str, str]:
        return {"x-ratelimit-requests-remaining": "90"}

    def _football(self, path: str, q: dict) -> HttpResponse:
        if path.endswith("/leagues"):
            return HttpResponse(200, self._hdr(), {"errors": [], "response": [{"league": {"id": 39, "name": "Premier League"}, "country": {"name": "England"}}] if q.get("name") == "Premier League" else []})
        if path.endswith("/fixtures"):
            if q.get("league") != "39":
                return HttpResponse(200, self._hdr(), {"errors": [], "response": []})
            resp = []
            for f in self.fixtures:
                if f["season"] != q.get("season"):
                    continue
                hg, ag = self.score(f)
                st = "FT" if hg is not None else "NS"
                resp.append({
                    "fixture": {"id": f["id"], "date": _iso(f["ko"]), "venue": {"name": "Stadium"}, "status": {"short": st}},
                    "teams": {"home": {"id": f["h"][0], "name": f["h"][1], "logo": None}, "away": {"id": f["a"][0], "name": f["a"][1], "logo": None}},
                    "goals": {"home": hg, "away": ag},
                    "score": {"fulltime": {"home": hg, "away": ag}},
                })
            return HttpResponse(200, self._hdr(), {"errors": [], "response": resp})
        if path.endswith("/injuries"):
            up = [f for f in self.fixtures if not self.played(f)][:3]
            resp = [{"player": {"name": f"Player {i}", "type": "Missing Fixture", "reason": "Knee Injury"}, "team": {"id": f["h"][0]}, "fixture": {"id": f["id"]}} for i, f in enumerate(up)]
            return HttpResponse(200, self._hdr(), {"errors": [], "response": resp})
        return HttpResponse(200, self._hdr(), {"errors": [], "response": []})

    def _basketball(self, path: str, q: dict) -> HttpResponse:
        if path.endswith("/leagues"):
            resp = [{"id": 12, "name": "NBA", "country": {"name": "USA"}}] if q.get("search") == "NBA" else []
            return HttpResponse(200, self._hdr(), {"errors": [], "response": resp})
        if path.endswith("/games"):
            if q.get("league") != "12":
                return HttpResponse(200, self._hdr(), {"errors": [], "response": []})
            resp = [
                {
                    "id": g["id"], "date": _iso(g["ko"]), "status": {"short": "FT" if self.played(g) else "NS"},
                    "teams": {"home": {"id": g["h"][0], "name": g["h"][1], "logo": None}, "away": {"id": g["a"][0], "name": g["a"][1], "logo": None}},
                    "scores": {"home": {"total": self.score(g)[0]}, "away": {"total": self.score(g)[1]}},
                }
                for g in self.games if g["season"] == q.get("season")
            ]
            return HttpResponse(200, self._hdr(), {"errors": [], "response": resp})
        return HttpResponse(200, self._hdr(), {"errors": [], "response": []})

    def _odds(self, path: str, q: dict) -> HttpResponse:
        if q.get("apiKey") != "test-odds":
            return HttpResponse(401, {}, {"message": "API key is not valid"})
        cost = len(q["markets"].split(",")) * len(q["regions"].split(","))
        self.odds_remaining -= cost
        hdr = {"x-requests-remaining": str(self.odds_remaining), "x-requests-last": str(cost)}
        rng = random.Random(zlib.crc32(f"{path}{self.now.isoformat()}".encode()))
        out = []
        horizon = self.now + timedelta(days=3)
        if "soccer_epl" in path:
            for f in self.fixtures:
                if self.played(f) or not (self.now < f["ko"] < horizon):
                    continue
                ph, pd, pa = self._fb_probs(f["lam"], f["mu"])
                skew = [math.exp(rng.gauss(0, self.odds_skew)) for _ in range(3)]
                fair = [p * s for p, s in zip((ph, pd, pa), skew)]
                tot = sum(fair)
                fair = [p / tot for p in fair]
                hn, an = ODDS_NAMES.get(f["h"][1], f["h"][1]), ODDS_NAMES.get(f["a"][1], f["a"][1])
                books = []
                for key, title, margin in (("pinnacle", "Pinnacle", 0.025), ("betclic_fr", "Betclic", 0.06), ("unibet_eu", "Unibet", 0.05)):
                    pr = [round(1 / (p * (1 + margin)), 2) for p in fair]
                    po = self._over(f["lam"] + f["mu"], 2.5) * math.exp(rng.gauss(0, self.odds_skew))
                    po = min(max(po, 0.05), 0.95)
                    books.append({"key": key, "title": title, "last_update": _iso(self.now - timedelta(minutes=5)), "markets": [
                        {"key": "h2h", "outcomes": [{"name": hn, "price": pr[0]}, {"name": "Draw", "price": pr[1]}, {"name": an, "price": pr[2]}]},
                        {"key": "totals", "outcomes": [{"name": "Over", "price": round(1 / (po * (1 + margin)), 2), "point": 2.5}, {"name": "Under", "price": round(1 / ((1 - po) * (1 + margin)), 2), "point": 2.5}]},
                    ]})
                out.append({"id": f"odds-{f['id']}", "sport_key": "soccer_epl", "commence_time": f["ko"].strftime("%Y-%m-%dT%H:%M:%SZ"), "home_team": hn, "away_team": an, "bookmakers": books})
        if "basketball_nba" in path:
            for g in self.games:
                if self.played(g) or not (self.now < g["ko"] < horizon):
                    continue
                line = math.floor(g["m"] + rng.gauss(0, 2)) + 0.5
                books = []
                for key, title, margin in (("pinnacle", "Pinnacle", 0.03), ("unibet_eu", "Unibet", 0.05)):
                    ph = 0.5 * math.erfc(-(g["m"] + rng.gauss(0, 1.5)) / (12 * math.sqrt(2)))  # P(home wins) = Phi(m / sigma)
                    books.append({"key": key, "title": title, "last_update": _iso(self.now), "markets": [
                        {"key": "h2h", "outcomes": [{"name": g["h"][1], "price": round(1 / (ph * (1 + margin)), 2)}, {"name": g["a"][1], "price": round(1 / ((1 - ph) * (1 + margin)), 2)}]},
                        {"key": "spreads", "outcomes": [{"name": g["h"][1], "price": 1.91, "point": -line}, {"name": g["a"][1], "price": 1.91, "point": line}]},
                        {"key": "totals", "outcomes": [{"name": "Over", "price": 1.9, "point": 225.5}, {"name": "Under", "price": 1.92, "point": 225.5}]},
                    ]})
                out.append({"id": f"odds-bb-{g['id']}", "sport_key": "basketball_nba", "commence_time": g["ko"].strftime("%Y-%m-%dT%H:%M:%SZ"), "home_team": g["h"][1], "away_team": g["a"][1], "bookmakers": books})
        return HttpResponse(200, hdr, out)

    @staticmethod
    def _fb_probs(lam: float, mu: float) -> tuple[float, float, float]:
        ph = pd = 0.0
        for i in range(11):
            for j in range(11):
                p = math.exp(-lam) * lam**i / math.factorial(i) * math.exp(-mu) * mu**j / math.factorial(j)
                if i > j:
                    ph += p
                elif i == j:
                    pd += p
        return ph, pd, 1 - ph - pd

    @staticmethod
    def _over(t: float, line: float) -> float:
        return 1 - sum(math.exp(-t) * t**k / math.factorial(k) for k in range(int(line) + 1))
