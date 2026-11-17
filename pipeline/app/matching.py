"""Match events between data sources (API-SPORTS fixtures vs The Odds API events) by time + team names."""
from __future__ import annotations

import re
import unicodedata
from datetime import timedelta
from difflib import SequenceMatcher
from typing import Iterable, TypeVar

_STOP = {"fc", "cf", "afc", "ac", "sc", "ssc", "as", "ss", "fk", "sk", "bc", "kk", "bk", "club", "de", "cd", "rc", "sl", "ud", "us", "1", "vfb", "vfl", "tsg", "rb"}

# Known naming differences between providers (normalised form -> normalised canonical).
_ALIASES = {
    "bayern munchen": "bayern munich",
    "inter milan": "inter",
    "internazionale": "inter",
    "paris saint germain": "psg",
    "paris sg": "psg",
    "wolverhampton wanderers": "wolves",
    "brighton and hove albion": "brighton",
    "brighton hove albion": "brighton",
    "tottenham hotspur": "tottenham",
    "west ham united": "west ham",
    "newcastle united": "newcastle",
    "manchester utd": "manchester united",
    "man united": "manchester united",
    "man city": "manchester city",
    "nottingham forest": "nottingham",
    "atletico madrid": "atletico",
    "athletic bilbao": "athletic",
    "borussia monchengladbach": "monchengladbach",
    "zalgiris kaunas": "zalgiris",
    "la lakers": "los angeles lakers",
    "la clippers": "los angeles clippers",
    "sporting cp": "sporting",
    "sporting lisbon": "sporting",
    "olympiacos piraeus": "olympiacos",
    "olympiakos": "olympiacos",
    "fenerbahce beko": "fenerbahce",
    "real madrid baloncesto": "real madrid",
}


def normalize(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = " ".join(w for w in s.split() if w not in _STOP)
    return _ALIASES.get(s, s)


def similarity(a: str, b: str) -> float:
    """Token-aware similarity. 'Manchester United' vs 'Manchester City' must stay low (shared city token)."""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ta, tb = set(na.split()), set(nb.split())
    if ta <= tb or tb <= ta:
        return 0.92
    if len(ta) == 1 and len(tb) == 1:
        return SequenceMatcher(None, na, nb).ratio()  # spelling variants: Olympiacos / Olympiakos
    return len(ta & tb) / len(ta | tb)


T = TypeVar("T")


def best_match(
    home: str,
    away: str,
    kickoff,
    candidates: Iterable[T],
    get=lambda c: (c.home_team, c.away_team, c.commence_time),
    window_h: float = 6.0,
    threshold: float = 0.72,
) -> T | None:
    """Best candidate with kickoff within `window_h` and mean name similarity >= threshold."""
    best, best_score = None, threshold
    for c in candidates:
        ch, ca, ct = get(c)
        if abs(ct - kickoff) > timedelta(hours=window_h):
            continue
        sh, sa = similarity(home, ch), similarity(away, ca)
        score = (sh + sa) / 2
        swapped = (similarity(home, ca) + similarity(away, ch)) / 2
        if swapped > score or min(sh, sa) < 0.5:
            continue  # sides swapped (reverse leg) or one side clearly a different team
        if score > best_score:
            best, best_score = c, score
    return best
