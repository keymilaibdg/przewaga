"""Official NBA injury report (free PDF published by the league several times a day).

URL: https://ak-static.cms.nba.com/referee/injury/Injury-Report_YYYY-MM-DD_HH_MMAM.pdf (US Eastern time, 15-minute
steps). The newest report is found by stepping back from "now". The PDF is a table:
Game Date | Game Time | Matchup | Team | Player Name | Current Status | Reason. Empty cells repeat the value above;
a long reason wraps onto lines above and below the player's row (the cell is vertically centred).
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
BASE = "https://ak-static.cms.nba.com/referee/injury/"
STATUSES = ("Out", "Doubtful", "Questionable", "Probable", "Available")
STATUS_PL = {"Out": "nie zagra", "Doubtful": "raczej nie zagra", "Questionable": "niepewny", "Probable": "raczej zagra", "Available": "dostępny"}
HEADERS = ("date", "time", "matchup", "team", "player", "status", "reason")
LINE_TOL = 2.5


@dataclass
class InjuryEntry:
    game_date: str  # MM/DD/YYYY (US Eastern)
    matchup: str  # 'HOU@IND' (away@home)
    team: str  # full team name from the report
    player: str  # 'Clint Capela'
    status: str  # Out | Doubtful | Questionable | Probable | Available
    reason: str
    top: float = 0.0

    @property
    def g_league(self) -> bool:
        return self.reason.startswith("G League")


def report_url(t: datetime) -> str:
    return f"{BASE}Injury-Report_{t.astimezone(ET).strftime('%Y-%m-%d_%I_%M%p')}.pdf"


def candidate_urls(now: datetime, steps: int = 48) -> Iterable[str]:
    """Newest first: 15-minute steps back from `now` (12 hours by default)."""
    et = now.astimezone(ET)
    t = et.replace(minute=et.minute - et.minute % 15, second=0, microsecond=0)
    for _ in range(steps):
        yield report_url(t)
        t -= timedelta(minutes=15)


def latest(now: datetime, get: Callable[[str], tuple[int, bytes]], steps: int = 48) -> tuple[str, bytes] | None:
    for url in candidate_urls(now, steps):
        status, body = get(url)
        if status == 200 and body[:4] == b"%PDF":
            return url, body
    return None


def display_name(name: str) -> str:
    """'Pippen Jr., Scotty' -> 'Scotty Pippen Jr.'; 'Udeh, Jr., Ernest' -> 'Ernest Udeh Jr.'."""
    parts = [p.strip() for p in name.split(",") if p.strip()]
    if len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    if len(parts) == 3:
        return f"{parts[2]} {parts[0]} {parts[1]}"
    return name.strip()


def parse_words(pages: list[list[dict]]) -> list[InjuryEntry]:
    """pages: words per page ({'text', 'x0', 'top'}), as pdfplumber's extract_words(x_tolerance=1) returns them."""
    entries: list[InjuryEntry] = []
    state = {"date": "", "time": "", "matchup": "", "team": ""}
    cols: list[tuple[float, str]] | None = None
    for words in pages:
        ws = sorted(words, key=lambda w: (w["top"], w["x0"]))
        lines: list[list[dict]] = []
        for w in ws:
            if lines and abs(lines[-1][0]["top"] - w["top"]) < LINE_TOL:
                lines[-1].append(w)
            else:
                lines.append([w])
        page_entries: list[InjuryEntry] = []
        fragments: list[tuple[float, str]] = []
        for line in lines:
            texts = [w["text"] for w in line]
            if "Matchup" in texts and "Reason" in texts:  # header: column positions
                xs = {w["text"]: w["x0"] for w in line}
                game = sorted(w["x0"] for w in line if w["text"] == "Game")
                cols = [(game[0], "date"), (game[1] if len(game) > 1 else xs["Matchup"] - 80, "time"), (xs["Matchup"], "matchup"), (xs["Team"], "team"),
                        (xs["Player"], "player"), (xs["Current"], "status"), (xs["Reason"], "reason")]
                continue
            if cols is None or texts[:2] == ["Injury", "Report:"] or texts[0] == "Page":
                continue
            cells: dict[str, list[str]] = {}
            for w in sorted(line, key=lambda w: w["x0"]):
                col = cols[0][1]
                for x, name in cols:
                    if w["x0"] + 2 >= x:
                        col = name
                cells.setdefault(col, []).append(w["text"])
            cell = {k: " ".join(v) for k, v in cells.items()}
            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", cell.get("date", "")):
                state["date"] = cell["date"]
            if cell.get("time"):
                state["time"] = cell["time"]
            if cell.get("matchup") and "@" in cell["matchup"]:
                state["matchup"] = cell["matchup"]
            if cell.get("team"):
                state["team"] = cell["team"]
            status = cell.get("status", "")
            if cell.get("player") and status in STATUSES:
                e = InjuryEntry(state["date"], state["matchup"], state["team"], display_name(cell["player"]), status, "", line[0]["top"])
                page_entries.append(e)
                if cell.get("reason"):
                    fragments.append((line[0]["top"], cell["reason"]))
            elif cell.get("reason") and not cell.get("player"):
                fragments.append((line[0]["top"], cell["reason"]))
        # wrapped reasons belong to the nearest player row on the page
        parts: dict[int, list[tuple[float, str]]] = {}
        for top, text in fragments:
            if not page_entries:
                continue
            i = min(range(len(page_entries)), key=lambda k: abs(page_entries[k].top - top))
            parts.setdefault(i, []).append((top, text))
        for i, frs in parts.items():
            page_entries[i].reason = " ".join(t for _, t in sorted(frs))
        entries += page_entries
    return entries


def parse_pdf(body: bytes) -> list[InjuryEntry]:
    import pdfplumber  # imported lazily: only the daily pipeline needs it

    with pdfplumber.open(io.BytesIO(body)) as pdf:
        pages = [[{"text": w["text"], "x0": w["x0"], "top": w["top"]} for w in p.extract_words(x_tolerance=1)] for p in pdf.pages]
    return parse_words(pages)
