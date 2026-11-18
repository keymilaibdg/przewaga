"""Match teams and events between data sources (football-data.org, CSV history, balldontlie, The Odds API)."""
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
    # football-data.co.uk CSV abbreviations
    "nott m forest": "nottingham",
    "nottm forest": "nottingham",
    "ath madrid": "atletico",
    "ath bilbao": "athletic",
    "espanol": "espanyol",
    "m gladbach": "monchengladbach",
    "mgladbach": "monchengladbach",
    "hamburger sv": "hamburg",
    "sheffield weds": "sheffield wednesday",
    # football-data.org long names
    "atletico de madrid": "atletico",
    "club atletico de madrid": "atletico",
    # UEFA cups (ETAP 5 cup ratings): API-Football / football-data.org / The Odds API / CSV spellings
    "olympique lyonnais": "lyon",
    "olympique lyon": "lyon",
    "olympique marseille": "marseille",
    "olympique de marseille": "marseille",
    "stade rennais": "rennes",
    "stade brestois 29": "brest",
    "stade brestois": "brest",
    "losc lille": "lille",
    "sp lisbon": "sporting",
    "sporting clube portugal": "sporting",
    "sp braga": "braga",
    "sporting braga": "braga",
    "sc braga": "braga",
    "red bull salzburg": "salzburg",
    "kobenhavn": "copenhagen",
    "union saint gilloise": "st gilloise",
    "union st gilloise": "st gilloise",
    "royale union saint gilloise": "st gilloise",
    "royale union sg": "st gilloise",
    "red star belgrade": "crvena zvezda",
    "ferencvarosi tc": "ferencvaros",
    "slavia prague": "slavia praha",
    "sparta prague": "sparta praha",
    "viktoria plzen": "plzen",
    "dynamo kiev": "dynamo kyiv",
    "ludogorets razgrad": "ludogorets",
    "qarabag agdam": "qarabag",
    "glasgow rangers": "rangers",
    "celtic glasgow": "celtic",
    "psv eindhoven": "psv",
    "az alkmaar": "az",
    "krc genk": "genk",
    "royal antwerp": "antwerp",
    "atalanta bc": "atalanta",
    "bsc young boys": "young boys",
    "bodo glimt": "bodo glimt",
    "fk bodo glimt": "bodo glimt",
    "legia warsaw": "legia",
    "legia warszawa": "legia",
    "lech poznan": "lech",
    "rakow czestochowa": "rakow",
    "jagiellonia bialystok": "jagiellonia",
}


# Letters that NFKD does not decompose into ASCII (they would be dropped: 'Łódź' -> 'odz').
_TRANSLIT = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ß": "ss", "æ": "ae", "Æ": "AE", "ı": "i"})


def ascii_fold(name: str) -> str:
    return unicodedata.normalize("NFKD", name.translate(_TRANSLIT)).encode("ascii", "ignore").decode()


def normalize(name: str) -> str:
    s = ascii_fold(name).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = " ".join(w for w in s.split() if w not in _STOP)
    return _ALIASES.get(s, s)


def similarity(a: str, b: str) -> float:
    """Token-aware similarity. 'Manchester United' vs 'Manchester City' must stay low (shared city token).

    1.0 equal; 0.92 all tokens of the shorter name present in the longer one ('Betis' / 'Real Betis');
    0.88 the same with abbreviated tokens ('Ein Frankfurt' / 'Eintracht Frankfurt', 'Gornik Z.' / 'Gornik Zabrze'),
    which needs at least one exact token; otherwise Jaccard on tokens or spelling ratio for single words.
    """
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
    short, long_ = (na.split(), nb.split()) if len(ta) <= len(tb) else (nb.split(), na.split())
    if _abbrev_cover(short, long_):
        return 0.88
    return len(ta & tb) / len(ta | tb)


def _abbrev_cover(short: list[str], long_: list[str]) -> bool:
    """Every token of `short` equals or abbreviates a distinct token of `long_`; at least one is exact."""
    rest, exact = list(long_), 0
    for t in short:
        if t in rest:
            rest.remove(t)
            exact += 1
            continue
        hit = next((u for u in rest if u.startswith(t)), None)
        if hit is None:
            return False
        rest.remove(hit)
    return exact >= 1


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
