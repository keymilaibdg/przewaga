"""Historical data for the backtest: download with a file cache, parse into plain records.

Sources (all free):
  football-data.co.uk   results + pre-match and closing odds (Pinnacle, Betfair Exchange, market max/average)
  sportsbookreviewsonline.com  NBA results + closing moneyline / spread / total (seasons 2019-20 .. 2022-23)
  API-Football (free key, seasons 2022-2024)   UEFA cup fixtures + team countries (cup ratings)

Downloads go to PRZEWAGA_BT_CACHE (default pipeline/backtest/cache, not committed; GitHub Actions keeps it in
actions/cache). Files of finished seasons never change, so they are fetched once.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import ROOT, season_for

CACHE = Path(os.environ.get("PRZEWAGA_BT_CACHE", ROOT / "pipeline" / "backtest" / "cache"))
FD_BASE = "https://www.football-data.co.uk"
SBR_BASE = "https://www.sportsbookreviewsonline.com/scoresoddsarchives"
AF_BASE = "https://v3.football.api-sports.io"
UK = ZoneInfo("Europe/London")
US_EAST = ZoneInfo("America/New_York")


class SourceError(RuntimeError):
    pass


# ---------------- download with cache ----------------

def fetch(url: str, name: str, headers: dict[str, str] | None = None, max_age_h: float | None = None, offline: bool = False) -> bytes:
    """Body of `url`, cached as CACHE/name. `max_age_h`: re-download when older (current-season files)."""
    path = CACHE / name
    if path.exists() and (offline or max_age_h is None or time.time() - path.stat().st_mtime < max_age_h * 3600):
        return path.read_bytes()
    if offline:
        raise SourceError(f"brak w pamięci podręcznej (tryb offline): {name}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (przewaga backtest)", **(headers or {})})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            return body
        except urllib.error.HTTPError as e:
            if e.code in (404, 403, 401):
                raise SourceError(f"{url}: HTTP {e.code}") from e
            err: Exception = e
        except Exception as e:  # noqa: BLE001 - network hiccup: retry
            err = e
        time.sleep(3 * (attempt + 1))
    raise SourceError(f"{url}: {err}")


def text(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


# ---------------- football-data.co.uk ----------------

def season_code(start_year: int) -> str:
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


@dataclass
class FbMatch:
    league: str  # our league key ('epl') or a football-data code for cup ratings ('I1', 'POL')
    kickoff: datetime  # UTC
    season: str  # '2024' = 2024/25 (calendar-year leagues: the year)
    home: str
    away: str
    hg: int
    ag: int
    # odds[(market, phase)] = prices; market 'h2h' -> (home, draw, away), 'ou25' -> (over, under);
    # phase 'ref' (sharp/low-margin book), 'best' (market maximum), 'avg', 'close_ref', 'close_best'
    odds: dict[tuple[str, str], tuple[float, ...]] = field(default_factory=dict)
    ref_source: dict[str, str] = field(default_factory=dict)  # market -> 'PS' | 'BFE' | 'Avg' (+ 'C' when closing)
    closing_only: bool = False  # file has closing odds only (extra leagues: Ekstraklasa)


H2H = ("H", "D", "A")
OU = (">2.5", "<2.5")
# Pre-match reference: Pinnacle; after Pinnacle left the files (2025): Betfair Exchange; last resort market average.
REF_PRE = ("PS", "BFE", "Avg", "BbAv")
REF_CLOSE = ("PSC", "BFEC", "AvgC")
BEST_PRE = ("Max", "BbMx")
BEST_CLOSE = ("MaxC",)
OU_REF_PRE = ("P", "BFE", "Avg", "BbAv")
OU_REF_CLOSE = ("PC", "BFEC", "AvgC")


def _f(v: str | None) -> float | None:
    try:
        x = float(v) if v not in (None, "") else None
    except ValueError:
        return None
    return x if x is not None and x > 1.0 else None


def _prices(row: dict[str, str], prefixes: tuple[str, ...], suffixes: tuple[str, ...]) -> tuple[tuple[float, ...], str] | None:
    for p in prefixes:
        vals = [_f(row.get(p + s)) for s in suffixes]
        if all(v is not None for v in vals):
            over = sum(1 / v for v in vals) - 1  # type: ignore[operator]
            if -0.05 <= over <= 0.30:  # garbage rows (swapped columns, 1.0 placeholders) are skipped
                return tuple(vals), p  # type: ignore[return-value]
    return None


def _best(best: tuple[float, ...] | None, avg: tuple[float, ...] | None) -> tuple[float, ...] | None:
    """Market maximum, with outliers (data errors, >25% above the average price) replaced by the average."""
    if best is None:
        return avg
    if avg is None:
        return best
    return tuple(b if b <= a * 1.25 else a for b, a in zip(best, avg))


def _kickoff(date: str, time_: str) -> datetime | None:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            d = datetime.strptime(date.strip(), fmt)
            break
        except ValueError:
            continue
    else:
        return None
    hh, mm = 15, 0
    if time_ and ":" in time_:
        try:
            hh, mm = (int(x) for x in time_.strip().split(":")[:2])
        except ValueError:
            pass
    return d.replace(hour=hh, minute=mm, tzinfo=UK).astimezone(timezone.utc)


def parse_fd(text_: str, league: str, calendar_year: bool = False) -> list[FbMatch]:
    """Rows with a result. Handles the per-season format (HomeTeam/FTHG) and the 'new/' format (Home/HG, closing only)."""
    out: list[FbMatch] = []
    for row in csv.DictReader(io.StringIO(text_)):
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        home, away = row.get("HomeTeam") or row.get("Home"), row.get("AwayTeam") or row.get("Away")
        hg = row.get("FTHG", row.get("HG"))
        ag = row.get("FTAG", row.get("AG"))
        ko = _kickoff(row.get("Date", ""), row.get("Time", ""))
        if not home or not away or ko is None or not (hg or "").isdigit() or not (ag or "").isdigit():
            continue
        m = FbMatch(league, ko, str(ko.year) if calendar_year else season_for("football", ko), home, away, int(hg), int(ag))  # type: ignore[arg-type]
        closing_only = "HomeTeam" not in row
        m.closing_only = closing_only
        avg = _prices(row, ("Avg", "BbAv"), H2H)
        ref = _prices(row, REF_PRE, H2H)
        best = _prices(row, BEST_PRE, H2H)
        cref = _prices(row, REF_CLOSE, H2H)
        cbest = _prices(row, BEST_CLOSE, H2H)
        cavg = _prices(row, ("AvgC",), H2H)
        if ref:
            m.odds[("h2h", "ref")], m.ref_source["h2h"] = ref
            m.odds[("h2h", "best")] = _best(best[0] if best else None, avg[0] if avg else None) or ref[0]
            if avg:
                m.odds[("h2h", "avg")] = avg[0]
        if cref:
            m.odds[("h2h", "close_ref")] = cref[0]
            m.odds[("h2h", "close_best")] = _best(cbest[0] if cbest else None, cavg[0] if cavg else None) or cref[0]
            if closing_only:  # Ekstraklasa: the only odds are closing odds
                m.odds[("h2h", "ref")], m.ref_source["h2h"] = cref[0], cref[1]
                m.odds[("h2h", "best")] = m.odds[("h2h", "close_best")]
                if cavg:
                    m.odds[("h2h", "avg")] = cavg[0]
        oref = _prices(row, OU_REF_PRE, OU)
        if oref:
            oavg = _prices(row, ("Avg", "BbAv"), OU)
            obest = _prices(row, ("Max", "BbMx"), OU)
            m.odds[("ou25", "ref")], m.ref_source["ou25"] = oref
            m.odds[("ou25", "best")] = _best(obest[0] if obest else None, oavg[0] if oavg else None) or oref[0]
            if oavg:
                m.odds[("ou25", "avg")] = oavg[0]
        ocref = _prices(row, OU_REF_CLOSE, OU)
        if ocref:
            m.odds[("ou25", "close_ref")] = ocref[0]
            ocbest = _prices(row, ("MaxC",), OU)
            ocavg = _prices(row, ("AvgC",), OU)
            m.odds[("ou25", "close_best")] = _best(ocbest[0] if ocbest else None, ocavg[0] if ocavg else None) or ocref[0]
        out.append(m)
    return out


def fd_season(code: str, start_year: int, league: str, current_start: int, offline: bool = False) -> list[FbMatch]:
    """One season of a per-season file (E0, SP1, ...)."""
    sc = season_code(start_year)
    raw = fetch(f"{FD_BASE}/mmz4281/{sc}/{code}.csv", f"fd/{sc}_{code}.csv", max_age_h=20 if start_year >= current_start else None, offline=offline)
    return parse_fd(text(raw), league)


def fd_extra(code: str, league: str, offline: bool = False) -> list[FbMatch]:
    """All seasons of an extra league ('POL', 'AUT', ...); file updated during the season."""
    raw = fetch(f"{FD_BASE}/new/{code}.csv", f"fd/new_{code}.csv", max_age_h=20, offline=offline)
    calendar = code in CALENDAR_YEAR_LEAGUES
    return parse_fd(text(raw), league, calendar_year=calendar)


# Leagues played within a calendar year (season label = year).
CALENDAR_YEAR_LEAGUES = {"NOR", "SWE", "FIN", "IRL", "USA", "BRA", "JPN", "CHN", "ARG"}


# ---------------- NBA: sportsbookreviewsonline.com ----------------

SBR_TEAMS = {
    "atlanta": "ATL", "boston": "BOS", "brooklyn": "BKN", "charlotte": "CHA", "chicago": "CHI", "cleveland": "CLE",
    "dallas": "DAL", "denver": "DEN", "detroit": "DET", "goldenstate": "GSW", "houston": "HOU", "indiana": "IND",
    "laclippers": "LAC", "lalakers": "LAL", "losangelesclippers": "LAC", "losangeleslakers": "LAL", "memphis": "MEM",
    "miami": "MIA", "milwaukee": "MIL", "minnesota": "MIN", "neworleans": "NOP", "newyork": "NYK",
    "oklahomacity": "OKC", "orlando": "ORL", "philadelphia": "PHI", "phoenix": "PHX", "portland": "POR",
    "sacramento": "SAC", "sanantonio": "SAS", "toronto": "TOR", "utah": "UTA", "washington": "WAS",
}


@dataclass
class NbaGame:
    date: datetime  # UTC, 19:30 US Eastern when the archive has no time
    season: str  # '2021-2022'
    home: str  # team abbreviation
    away: str
    hp: int
    ap: int
    neutral: bool
    ml: tuple[float, float] | None  # decimal (home, away), closing consensus
    spread_home: float | None  # closing line for the home side (e.g. -5.5)
    total: float | None  # closing total points


def american(v: str) -> float | None:
    try:
        a = float(v)
    except ValueError:
        return None
    if a == 0 or abs(a) < 100:
        return None
    return 1 + a / 100 if a > 0 else 1 + 100 / abs(a)


def _line(v: str) -> float | None:
    v = v.strip().lower()
    if v in ("pk", "p"):
        return 0.0
    try:
        return float(v)
    except ValueError:
        return None


def parse_sbr(html: str, season: str) -> list[NbaGame]:
    """Archive table: rows Date, Rot, VH, Team, 1st..4th, Final, Open, Close, ML, 2H; two rows per game.

    In the Close column the favourite's row carries the spread, the other row the total (the larger number).
    """
    start = int(season[:4])
    rows: list[list[str]] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if len(cells) >= 12 and cells[0].isdigit():
            rows.append(cells)
    out: list[NbaGame] = []
    i = 0
    while i + 1 < len(rows):
        v, h = rows[i], rows[i + 1]
        if v[2] not in ("V", "N") or h[2] not in ("H", "N") or v[0] != h[0]:
            i += 1
            continue
        i += 2
        tv, th = SBR_TEAMS.get(re.sub(r"[^a-z]", "", v[3].lower())), SBR_TEAMS.get(re.sub(r"[^a-z]", "", h[3].lower()))
        if not tv or not th or not v[8].isdigit() or not h[8].isdigit():
            continue
        mmdd = v[0].zfill(4)
        month, day = int(mmdd[:2]), int(mmdd[2:])
        year = start if month >= 8 else start + 1
        try:
            date = datetime(year, month, day, 19, 30, tzinfo=US_EAST).astimezone(timezone.utc)
        except ValueError:
            continue
        cv, ch = _line(v[10]), _line(h[10])
        spread_home = total = None
        if cv is not None and ch is not None:
            if cv > ch:  # visitor row has the total, home is the favourite
                total, spread_home = cv, -abs(ch)
            else:
                total, spread_home = ch, abs(cv)
            if total < 150 or abs(spread_home) > 30:
                total = spread_home = None
        mv, mh = american(v[11]), american(h[11])
        out.append(NbaGame(date, f"{start}-{start + 1}", th, tv, int(h[8]), int(v[8]), v[2] == "N", (mh, mv) if mv and mh else None, spread_home, total))
    return out


def sbr_season(season: str, offline: bool = False) -> list[NbaGame]:
    s = f"{season[:4]}-{season[-2:]}"
    raw = fetch(f"{SBR_BASE}/nba-odds-{s}/", f"sbr/nba_{s}.html", offline=offline)
    return parse_sbr(text(raw), season)


# ---------------- API-Football: UEFA cups 2022-2024 ----------------

CUP_LEAGUES = {2: "ucl", 3: "uel", 848: "uecl"}
CUP_SEASONS = (2022, 2023, 2024)
CUPS_FILE = ROOT / "pipeline" / "backtest" / "data" / "uefa_cups_2022_2024.json"


@dataclass
class CupMatch:
    comp: str  # ucl | uel | uecl
    kickoff: datetime
    home: str
    away: str
    home_country: str | None
    away_country: str | None
    hg: int
    ag: int
    neutral: bool = False  # finals


def cups(key: str | None, offline: bool = False) -> list[CupMatch]:
    """Cup fixtures 2022-2024 (18 API calls once; the result is committed as a small JSON file)."""
    if not CUPS_FILE.exists():
        if offline or not key:
            return []
        data: dict[str, list] = {"fixtures": [], "teams": []}
        for lid in CUP_LEAGUES:
            for season in CUP_SEASONS:
                for ep in ("fixtures", "teams"):
                    raw = fetch(f"{AF_BASE}/{ep}?league={lid}&season={season}", f"af/{ep}_{lid}_{season}.json", {"x-apisports-key": key})
                    body = json.loads(raw)
                    if body.get("errors"):
                        raise SourceError(f"API-Football {ep} {lid}/{season}: {body['errors']}")
                    for r in body.get("response", []):
                        if ep == "teams":
                            data["teams"].append({"id": r["team"]["id"], "name": r["team"]["name"], "country": r["team"].get("country")})
                        else:
                            ft = (r.get("score") or {}).get("fulltime") or {}
                            if ft.get("home") is None or r["fixture"]["status"]["short"] not in ("FT", "AET", "PEN"):
                                continue
                            data["fixtures"].append(
                                {
                                    "comp": CUP_LEAGUES[lid],
                                    "date": r["fixture"]["date"],
                                    "round": r["league"].get("round"),
                                    "home_id": r["teams"]["home"]["id"],
                                    "away_id": r["teams"]["away"]["id"],
                                    "hg": ft["home"],
                                    "ag": ft["away"],
                                }
                            )
        CUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
        CUPS_FILE.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    data = json.loads(CUPS_FILE.read_text(encoding="utf-8"))
    teams = {t["id"]: t for t in data["teams"]}
    out = []
    for f in data["fixtures"]:
        th, ta = teams.get(f["home_id"]), teams.get(f["away_id"])
        if not th or not ta:
            continue
        out.append(
            CupMatch(
                f["comp"],
                datetime.fromisoformat(f["date"].replace("Z", "+00:00")).astimezone(timezone.utc),
                th["name"],
                ta["name"],
                th.get("country"),
                ta.get("country"),
                int(f["hg"]),
                int(f["ag"]),
                neutral=(f.get("round") or "").lower() == "final",
            )
        )
    return out
