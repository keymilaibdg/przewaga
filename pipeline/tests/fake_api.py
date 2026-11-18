"""Offline fake of football-data.org, football-data.co.uk CSV, balldontlie and The Odds API (realistic shapes).

A small synthetic world: Premier League and NBA (previous + current season) with results generated from known
team strengths, odds that sometimes misprice so the engine has something to find, and two Europa League games
known only from The Odds API (/events, /odds, /scores) to exercise the odds-only path.
Every source spells team names its own way, as in reality.
"""
from __future__ import annotations

import math
import random
import urllib.parse
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.providers.http import HttpResponse

FB_TEAMS = [
    (33, "Manchester United", 1.15, 0.95), (40, "Liverpool", 1.45, 0.80), (42, "Arsenal", 1.40, 0.75),
    (49, "Chelsea", 1.20, 0.90), (50, "Manchester City", 1.45, 0.80), (47, "Tottenham", 1.15, 1.05),
    (34, "Newcastle", 1.10, 0.95), (66, "Aston Villa", 1.10, 1.00), (51, "Brighton", 1.05, 1.05),
    (48, "West Ham", 0.95, 1.15),
]
# Each source spells some names differently — the matcher and the team resolver must cope.
ODDS_NAMES = {"Tottenham": "Tottenham Hotspur", "Newcastle": "Newcastle United", "Brighton": "Brighton and Hove Albion", "West Ham": "West Ham United"}
FDO_NAMES = {"Tottenham": "Tottenham Hotspur FC", "Newcastle": "Newcastle United FC", "Brighton": "Brighton & Hove Albion FC", "West Ham": "West Ham United FC"}
CSV_NAMES = {"Manchester United": "Man United", "Manchester City": "Man City"}
UEL = [("Roma", "Porto", 30), ("Lyon", "Real Betis", 33)]  # home, away, hours after the first NOW
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
    serve_injuries: bool = False  # official NBA injury report (binary PDF via get_raw)
    clubelo_down: bool = False

    def __post_init__(self) -> None:
        rng = random.Random(self.seed)
        self.uel = [{"id": f"uel-{i}", "h": h, "a": a, "ko": self.now + timedelta(hours=dh), "_hg": 1 + i, "_ag": 1} for i, (h, a, dh) in enumerate(UEL)]
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
        if u.netloc == "api.football-data.org":
            if headers.get("X-Auth-Token") != "test-fdo":
                return HttpResponse(403, {}, {"message": "The resource you are looking for is restricted. Please pass a valid API token.", "errorCode": 403})
            return self._fdo(path)
        if u.netloc == "www.football-data.co.uk":
            return self._csv(path)
        if u.netloc == "api.balldontlie.io":
            if headers.get("Authorization") != "test-bdl":
                return HttpResponse(401, {}, {"error": "Unauthorized"})
            return self._bdl(q)
        if "the-odds-api.com" in u.netloc:
            return self._odds(path, q)
        if u.netloc == "api.clubelo.com":
            if self.clubelo_down:
                return HttpResponse(502, {"content-type": "text/html"}, "<html>Bad Gateway</html>")
            rows = ["Rank,Club,Country,Level,Elo,From,To"] + [
                f"{i + 1},{CSV_NAMES.get(t[1], t[1])},ENG,1,{1500 + 300 * (t[2] - t[3]):.1f},2026-11-01,2026-11-30" for i, t in enumerate(FB_TEAMS)
            ] + ["99,Roma,ITA,1,1780.0,2026-11-01,2026-11-30", "120,Porto,POR,1,1750.0,2026-11-01,2026-11-30"]
            return HttpResponse(200, {"content-type": "text/csv"}, "\n".join(rows) + "\n")
        return HttpResponse(404, {}, {"message": "not found"})

    # ---- official NBA injury report (binary) ----
    def get_raw(self, url: str) -> tuple[int, bytes]:
        self.calls.append(url)
        if not self.serve_injuries or "Injury-Report_" not in url:
            return 404, b""
        return 200, b"%PDF-fake"

    def parse_injury_pdf(self, body: bytes):  # noqa: ANN201 - test double for nba_injuries.parse_pdf
        from app.providers.nba_injuries import InjuryEntry

        et = self.now.astimezone(ZoneInfo("America/New_York"))
        games = sorted((g for g in self.games if g["ko"] > self.now), key=lambda g: g["ko"])[:1]
        out = []
        for g in games:
            d = g["ko"].astimezone(ZoneInfo("America/New_York")).strftime("%m/%d/%Y")
            out.append(InjuryEntry(d, "X@Y", g["h"][1], "Star Player", "Out", "Injury/Illness - Left Knee Sprain"))
            out.append(InjuryEntry(d, "X@Y", g["a"][1], "Bench Guy", "Questionable", "Injury/Illness - Illness"))
            out.append(InjuryEntry(d, "X@Y", g["a"][1], "Two Way", "Out", "G League - Two-Way"))
        _ = et
        return out

    def _fdo(self, path: str) -> HttpResponse:
        hdr = {"x-requests-available-minute": "9"}
        if not path.endswith("/competitions/PL/matches"):
            return HttpResponse(200, hdr, {"matches": []})
        team = lambda t: {"id": t[0], "name": FDO_NAMES.get(t[1], t[1] + " FC"), "shortName": t[1], "tla": t[1][:3].upper(), "crest": f"https://crests.example/{t[0]}.png"}  # noqa: E731
        matches = []
        for f in self.fixtures:
            if f["season"] != "2026":
                continue
            hg, ag = self.score(f)
            matches.append({"id": f["id"], "utcDate": f["ko"].strftime("%Y-%m-%dT%H:%M:%SZ"), "status": "FINISHED" if hg is not None else "TIMED", "venue": "Stadium",
                            "homeTeam": team(f["h"]), "awayTeam": team(f["a"]), "score": {"duration": "REGULAR", "fullTime": {"home": hg, "away": ag}}})
        return HttpResponse(200, hdr, {"matches": matches})

    def _csv(self, path: str) -> HttpResponse:
        season = {"/mmz4281/2526/E0.csv": "2025", "/mmz4281/2627/E0.csv": "2026"}.get(path)
        if season is None:
            return HttpResponse(404, {"content-type": "text/html"}, "<html>Not Found</html>")
        uk = ZoneInfo("Europe/London")
        lines = ["Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,PSCH,PSCD,PSCA"]
        for f in self.fixtures:
            hg, ag = self.score(f)
            if f["season"] != season or hg is None:
                continue
            ko = f["ko"].astimezone(uk)
            name = lambda t: CSV_NAMES.get(t[1], t[1])  # noqa: E731
            lines.append(f"E0,{ko:%d/%m/%Y},{ko:%H:%M},{name(f['h'])},{name(f['a'])},{hg},{ag},{'H' if hg > ag else 'D' if hg == ag else 'A'},2.0,3.4,3.8")
        return HttpResponse(200, {"content-type": "text/csv"}, "\n".join(lines) + "\n")

    def _bdl(self, q: dict) -> HttpResponse:
        season = int(q["seasons[]"])
        games = [g for g in self.games if int(g["season"][:4]) == season]
        if "start_date" in q:
            lo, hi = q["start_date"], q.get("end_date", "9999")
            games = [g for g in games if lo <= g["ko"].date().isoformat() <= hi]
        per, start = int(q.get("per_page", 25)), int(q.get("cursor", 0))
        page = games[start:start + per]
        team = lambda t: {"id": t[0], "full_name": t[1], "name": t[1].split()[-1], "abbreviation": t[1][:3].upper()}  # noqa: E731
        data = []
        for g in page:
            hp, ap = self.score(g)
            data.append({"id": g["id"], "date": g["ko"].date().isoformat(), "datetime": g["ko"].strftime("%Y-%m-%dT%H:%M:%S.000Z"), "season": season,
                         "status": "Final" if hp is not None else g["ko"].strftime("%Y-%m-%dT%H:%M:%SZ"), "period": 4 if hp is not None else 0,
                         "home_team_score": hp or 0, "visitor_team_score": ap or 0, "home_team": team(g["h"]), "visitor_team": team(g["a"])})
        meta = {"per_page": per, **({"next_cursor": start + per} if start + per < len(games) else {})}
        return HttpResponse(200, {"x-ratelimit-remaining": "4"}, {"data": data, "meta": meta})

    def _odds(self, path: str, q: dict) -> HttpResponse:
        if q.get("apiKey") != "test-odds":
            return HttpResponse(401, {}, {"message": "API key is not valid"})
        if path.endswith("/events"):
            hdr = {"x-requests-remaining": str(self.odds_remaining), "x-requests-last": "0"}
            evs = [{"id": e["id"], "sport_key": "soccer_uefa_europa_league", "commence_time": e["ko"].strftime("%Y-%m-%dT%H:%M:%SZ"), "home_team": e["h"], "away_team": e["a"]}
                   for e in self.uel if "europa" in path and e["ko"] > self.now]
            return HttpResponse(200, hdr, evs)
        if path.endswith("/scores"):
            self.odds_remaining -= 2
            hdr = {"x-requests-remaining": str(self.odds_remaining), "x-requests-last": "2"}
            out = []
            for e in self.uel if "europa" in path else []:
                done = e["ko"] + timedelta(hours=2.5) < self.now
                out.append({"id": e["id"], "sport_key": "soccer_uefa_europa_league", "commence_time": e["ko"].strftime("%Y-%m-%dT%H:%M:%SZ"), "completed": done,
                            "home_team": e["h"], "away_team": e["a"], "scores": [{"name": e["h"], "score": str(e["_hg"])}, {"name": e["a"], "score": str(e["_ag"])}] if done else None})
            return HttpResponse(200, hdr, out)
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
        if "europa" in path:
            for e in self.uel:
                if not (self.now < e["ko"] < horizon):
                    continue
                books = [{"key": key, "title": title, "last_update": _iso(self.now - timedelta(minutes=5)), "markets": [
                    {"key": "h2h", "outcomes": [{"name": e["h"], "price": round(2.3 * m, 2)}, {"name": "Draw", "price": round(3.3 * m, 2)}, {"name": e["a"], "price": round(3.2 * m, 2)}]},
                    {"key": "totals", "outcomes": [{"name": "Over", "price": round(1.95 * m, 2), "point": 2.5}, {"name": "Under", "price": round(1.85 * m, 2), "point": 2.5}]},
                ]} for key, title, m in (("pinnacle", "Pinnacle", 1.0), ("unibet_eu", "Unibet", 0.97))]
                out.append({"id": e["id"], "sport_key": "soccer_uefa_europa_league", "commence_time": e["ko"].strftime("%Y-%m-%dT%H:%M:%SZ"), "home_team": e["h"], "away_team": e["a"], "bookmakers": books})
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
