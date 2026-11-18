"""Price insight: where does a price come from, is it justified, is it worth taking, how risky is it.

Built for every 1X2 / moneyline selection with odds, with a focus on short prices (1.20-1.60) that often look like
"sure things". Everything is computed from data the pipeline already has: the bookmakers' quotes and their history,
the model's team strengths, recent results, the schedule, and the historical record of similar prices
(app/price_buckets.json, written by the backtest).
"""
from __future__ import annotations

import json
import math
import sqlite3
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .analysis import EventAnalysis, parse, team_form
from .config import LEAGUE_BY_KEY, season_for
from .engine.evaluate import Selection
from .models.basketball import Ratings
from .models.football import DixonColes, outcome_probs, score_matrix

PRICE_BUCKETS_PATH = Path(__file__).resolve().parent / "price_buckets.json"
TAX = 0.12
FORM_N = 5


def load_buckets(path: Path | None = None) -> dict[str, Any]:
    try:
        return json.loads((path or PRICE_BUCKETS_PATH).read_text(encoding="utf-8")).get("leagues", {})
    except (OSError, ValueError):
        return {}


def pl(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def pct(x: float, d: int = 0) -> str:
    return f"{100 * x:.{d}f}%".replace(".", ",")


def spct(x: float, d: int = 1) -> str:
    return ("+" if x > 0 else "−" if x < 0 else "") + pct(abs(x), d)


# ---------------- team strength ----------------


@dataclass
class Strength:
    value: dict[str, float]  # team id -> strength (higher = better)
    rank: dict[str, int]  # 1 = strongest
    size: int
    unit: str


def strengths(model: DixonColes | Ratings | None) -> Strength | None:
    if isinstance(model, DixonColes) and len(model.teams):
        val = {t: float(model.att[i] - model.dfn[i]) for i, t in enumerate(model.teams) if model.known(t)}
        unit = "gole"
    elif isinstance(model, Ratings) and model.rating:
        val = {t: v for t, v in model.rating.items() if model.known(t)}
        unit = "pkt"
    else:
        return None
    order = sorted(val, key=lambda t: -val[t])
    return Strength(val, {t: i + 1 for i, t in enumerate(order)}, len(order), unit)


# ---------------- factors ----------------


def _form(conn: sqlite3.Connection, tid: str, before: str, n: int = FORM_N) -> list[dict[str, Any]]:
    out = []
    for r in team_form(conn, tid, before, n):
        home = r["home_team_id"] == tid
        s, c = (r["home_score"], r["away_score"]) if home else (r["away_score"], r["home_score"])
        out.append({"opp": r["away_team_id"] if home else r["home_team_id"], "home": home, "s": s, "c": c, "res": "W" if s > c else "D" if s == c else "L"})
    return out


def _venue_record(conn: sqlite3.Connection, tid: str, league: str, season: str, home: bool, before: str) -> tuple[int, int, int]:
    col = "home_team_id" if home else "away_team_id"
    rows = conn.execute(
        f"SELECT home_score, away_score FROM events WHERE league_key = ? AND season = ? AND {col} = ? AND status = 'finished' AND home_score IS NOT NULL AND kickoff < ?",
        (league, season, tid, before),
    ).fetchall()
    w = d = l_ = 0
    for r in rows:
        s, c = (r["home_score"], r["away_score"]) if home else (r["away_score"], r["home_score"])
        w, d, l_ = w + (s > c), d + (s == c), l_ + (s < c)
    return w, d, l_


def _h2h(conn: sqlite3.Connection, h: str, a: str, before: str) -> tuple[int, int, int]:
    rows = conn.execute(
        """SELECT home_team_id, home_score, away_score FROM events WHERE status = 'finished' AND kickoff < ? AND home_score IS NOT NULL
           AND ((home_team_id = ? AND away_team_id = ?) OR (home_team_id = ? AND away_team_id = ?)) ORDER BY kickoff DESC LIMIT 5""",
        (before, h, a, a, h),
    ).fetchall()
    hw = d = aw = 0
    for r in rows:
        hs, as_ = (r["home_score"], r["away_score"]) if r["home_team_id"] == h else (r["away_score"], r["home_score"])
        hw, d, aw = hw + (hs > as_), d + (hs == as_), aw + (hs < as_)
    return hw, d, aw


def factor(key: str, title: str, home: str, away: str, favours: str, note: str = "") -> dict[str, str]:
    return {"key": key, "title": title, "home": home, "away": away, "favours": favours, "note": note}


def factors(conn: sqlite3.Connection, a: EventAnalysis, model: DixonColes | Ratings | None, st: Strength | None) -> tuple[list[dict[str, str]], dict[str, Any]]:
    ev = a.event
    h, w, ko = ev["home_team_id"], ev["away_team_id"], ev["kickoff"]
    is_fb = ev["sport"] == "football"
    close = 1 if is_fb else 5  # a loss "on the edge": by one goal / by up to 5 points
    out: list[dict[str, str]] = []
    facts: dict[str, Any] = {}

    if st and h in st.rank and w in st.rank:
        rh, ra = st.rank[h], st.rank[w]
        vh, va = st.value[h], st.value[w]
        unit = "siła ataku − obrony" if is_fb else "pkt ponad średnią"
        out.append(factor("strength", "Siła z całego okresu (model)", f"{rh}. z {st.size} ({pl(vh, 2) if is_fb else pl(vh)})", f"{ra}. z {st.size} ({pl(va, 2) if is_fb else pl(va)})",
                          "home" if rh < ra else "away" if ra < rh else "none", f"Ocena z ok. dwóch sezonów z wagą czasową ({unit}); rynek patrzy głównie na nią, nie na ostatnie 5 meczów."))
        facts["rank"] = (rh, ra, st.size)

    fh, fa = _form(conn, h, ko), _form(conn, w, ko)
    if fh or fa:
        def fmt(f: list[dict]) -> str:
            return "".join(x["res"] for x in f).replace("W", "W").replace("D", "R").replace("L", "P") or "—"

        def pts(f: list[dict]) -> float:
            return sum(3 if x["res"] == "W" else 1 if x["res"] == "D" else 0 for x in f) / len(f) if f else 0.0

        sh, sa = pts(fh), pts(fa)
        out.append(factor("form", f"Forma (ostatnie {FORM_N})", fmt(fh), fmt(fa), "home" if sh > sa + 0.3 else "away" if sa > sh + 0.3 else "none",
                          "W – wygrana, R – remis, P – porażka; od najnowszego. Krótka seria w dużej mierze zależy od przypadku i terminarza."))
        facts["losses"] = (sum(x["res"] == "L" for x in fh), sum(x["res"] == "L" for x in fa))

        if st:
            def opp_rank(f: list[dict]) -> float | None:
                rs = [st.rank[x["opp"]] for x in f if x["opp"] in st.rank]
                return sum(rs) / len(rs) if rs else None

            oh, oa = opp_rank(fh), opp_rank(fa)
            if oh is not None and oa is not None:
                out.append(factor("schedule_strength", "Siła rywali w tych meczach", f"śr. {pl(oh)}. drużyna", f"śr. {pl(oa)}. drużyna",
                                  "home" if oh < oa - 2 else "away" if oa < oh - 2 else "none",
                                  "Niższe miejsce = silniejsi rywale. Porażki z czołówką mówią o drużynie mniej niż porażki ze słabymi."))
                facts["opp_rank"] = (oh, oa)

        def diff(f: list[dict]) -> int:
            return sum(x["s"] - x["c"] for x in f)

        def tight(f: list[dict]) -> int:
            return sum(1 for x in f if x["res"] == "L" and x["c"] - x["s"] <= close)

        dh, da = diff(fh), diff(fa)
        out.append(factor("margins", "Bilans i porażki na styk", f"{dh:+d}, na styk: {tight(fh)}/{sum(x['res'] == 'L' for x in fh)}", f"{da:+d}, na styk: {tight(fa)}/{sum(x['res'] == 'L' for x in fa)}",
                          "home" if dh > da else "away" if da > dh else "none",
                          f"Bilans {'bramek' if is_fb else 'punktów'} w ostatnich {FORM_N}; „na styk” = porażka różnicą {'jednego gola' if is_fb else 'do 5 pkt'} (często pech, nie słabość)."))
        facts["tight"] = (tight(fh), tight(fa))

    season = season_for(ev["sport"], parse(ko))
    hw_, hd, hl = _venue_record(conn, h, ev["league_key"], season, True, ko)
    aw_, ad, al = _venue_record(conn, w, ev["league_key"], season, False, ko)
    if hw_ + hd + hl + aw_ + ad + al:
        rec = (lambda w_, d, l_: f"{w_}-{d}-{l_}") if is_fb else (lambda w_, d, l_: f"{w_}-{l_}")
        out.append(factor("venue", "W tym sezonie: gospodarz u siebie / gość na wyjeździe", rec(hw_, hd, hl), rec(aw_, ad, al),
                          "home" if (hw_ + 0.5 * hd) / max(1, hw_ + hd + hl) > (aw_ + 0.5 * ad) / max(1, aw_ + ad + al) else "away", "Wygrane-remisy-porażki." if is_fb else "Wygrane-porażki."))

    if isinstance(model, DixonColes) and h in model.teams and w in model.teams:
        lam, mu = model.rates(h, w)
        ln, mn = model.rates(h, w, neutral=True)
        p_home = outcome_probs(score_matrix(lam, mu, model.rho))["home"]
        p_neutral = outcome_probs(score_matrix(ln, mn, model.rho))["home"]
        out.append(factor("home_adv", "Przewaga własnego boiska", f"+{pct(p_home - p_neutral)} szansy", "—", "home",
                          f"O tyle rośnie szansa gospodarza dzięki grze u siebie (model: oczekiwane gole {pl(lam, 2)} – {pl(mu, 2)})."))
    elif isinstance(model, Ratings) and model.rating:
        out.append(factor("home_adv", "Przewaga własnej hali", f"+{pl(model.hca)} pkt", "—", "home", "Średnia przewaga gospodarza w NBA w danych modelu."))

    hh, hd2, ha = _h2h(conn, h, w, ko)
    if hh + hd2 + ha:
        out.append(factor("h2h", "Bezpośrednie mecze (ostatnie 5)", str(hh), str(ha), "home" if hh > ha else "away" if ha > hh else "none",
                          f"Remisy: {hd2}. Mała próba, często sprzed zmian w składach — rynek przywiązuje do tego niewielką wagę." if is_fb else "Mała próba — rynek przywiązuje do tego niewielką wagę."))

    if ev["sport"] == "basketball":
        inj = conn.execute(
            """SELECT team_id, player, kind FROM injuries WHERE league_key = 'nba' AND fixture_event_id = ?
               AND kind IN ('Out', 'Doubtful', 'Questionable') AND (reason IS NULL OR reason NOT LIKE 'G League%')""",
            (ev["id"],),
        ).fetchall()
        reported = conn.execute("SELECT 1 FROM injuries WHERE league_key = 'nba' LIMIT 1").fetchone()
        if reported:
            def who(tid: str) -> tuple[str, int]:
                out = [r["player"] for r in inj if r["team_id"] == tid and r["kind"] == "Out"]
                unsure = [r["player"] for r in inj if r["team_id"] == tid and r["kind"] != "Out"]
                txt = (f"nie zagra: {len(out)}" + (f" ({', '.join(out[:3])}{'…' if len(out) > 3 else ''})" if out else "")) + (f"; niepewni: {len(unsure)}" if unsure else "")
                return txt, len(out)

            th, nh = who(h)
            ta, na = who(w)
            out.append(factor("injuries", "Nieobecni (oficjalny raport NBA)", th, ta, "home" if na > nh + 1 else "away" if nh > na + 1 else "none",
                              "Bez wagi zawodników: brak lidera znaczy dużo więcej niż brak rezerwowego. Rynek zna wagę — jeśli kurs mocno się ruszył, to często przez tę listę."))
            facts["injuries"] = (nh, na)

    if ev["sport"] == "football":
        eh, ea_ = clubelo_rating(conn, h, ev["home_name"], ev["league_key"]), clubelo_rating(conn, w, ev["away_name"], ev["league_key"])
        if eh and ea_:
            out.append(factor("clubelo", "ClubElo (niezależny ranking)", f"{eh[0]:.0f}" + (f" ({eh[1]}. w Europie)" if eh[1] else ""), f"{ea_[0]:.0f}" + (f" ({ea_[1]}. w Europie)" if ea_[1] else ""),
                              "home" if eh[0] > ea_[0] + 25 else "away" if ea_[0] > eh[0] + 25 else "none",
                              f"Różnica {eh[0] - ea_[0]:+.0f} pkt Elo. Ranking clubelo.com liczony z wyników wszystkich klubów Europy — drugie, niezależne zdanie obok naszego modelu."))

    if a.schedule:
        c = a.schedule

        def sched(t) -> str:  # noqa: ANN001
            parts = ["drugi dzień z rzędu" if t.b2b else f"{days_pl(t.rest_days)} przerwy"]
            if t.travel_km >= 300:
                parts.append(f"podróż {round(t.travel_km, -1):.0f} km")
            parts.append(f"{games_pl(t.games_last_7d)} w 7 dni")
            return ", ".join(parts)

        tired_h = c.home.b2b * 2 + (c.home.travel_km > 1500) + (c.home.games_last_7d >= 4)
        tired_a = c.away.b2b * 2 + (c.away.travel_km > 1500) + (c.away.games_last_7d >= 4)
        used = isinstance(model, Ratings) and bool(model.fatigue)
        out.append(factor("fatigue", "Zmęczenie i terminarz", sched(c.home), sched(c.away), "home" if tired_a > tired_h else "away" if tired_h > tired_a else "none",
                          "Uwzględnione w modelu (backtest potwierdził)." if used else "Pokazane informacyjnie; backtest zdecyduje, czy model ma to liczyć."))
        facts["fatigue"] = (tired_h, tired_a)
    elif is_fb:
        def days_since(f_tid: str) -> float | None:
            r = conn.execute("SELECT MAX(kickoff) AS k FROM events WHERE (home_team_id = ? OR away_team_id = ?) AND status = 'finished' AND kickoff < ?", (f_tid, f_tid, ko)).fetchone()
            return (parse(ko) - parse(r["k"])).total_seconds() / 86400 if r and r["k"] else None

        dh_, da_ = days_since(h), days_since(w)
        if dh_ is not None and da_ is not None and min(dh_, da_) < 5:
            out.append(factor("rest", "Dni od ostatniego meczu", f"{pl(dh_, 0)}", f"{pl(da_, 0)}", "home" if dh_ > da_ + 1 else "away" if da_ > dh_ + 1 else "none",
                              "Mecz w środku tygodnia (puchary) przed spotkaniem oznacza mniej odpoczynku i częstszą rotację składu."))
    return out, facts


def clubelo_rating(conn: sqlite3.Connection, team_id: str, name: str, league: str) -> tuple[float, int | None] | None:
    """(Elo, rank) of a team from the latest ClubElo download, matched by name (within the country for domestic leagues)."""
    from .matching import similarity
    from .providers.clubelo import LEAGUE_COUNTRY

    country = LEAGUE_COUNTRY.get(league)
    rows = conn.execute("SELECT club, country, elo, rank FROM clubelo" + (" WHERE country = ?" if country else ""), ((country,) if country else ())).fetchall()
    if not rows:
        return None
    names = {name} | {r["name"] for r in conn.execute("SELECT name FROM team_aliases WHERE team_id = ?", (team_id,))}
    scored = sorted(((max(similarity(n, r["club"]) for n in names), r) for r in rows), key=lambda x: -x[0])
    if not scored or scored[0][0] < 0.85 or (len(scored) > 1 and scored[1][0] >= scored[0][0]):
        return None
    r = scored[0][1]
    return float(r["elo"]), r["rank"]


# ---------------- per-selection numbers ----------------


def _binom_loss_prob(n: int, p: float, price: float) -> float:
    """P(total profit < 0 after n bets of 1 unit at `price` after tax), wins ~ Binomial(n, p)."""
    need = n / (price * (1 - TAX))  # wins needed to break even
    return sum(math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(n + 1) if k < need)


def selection_insight(s: Selection, league: str, buckets: dict[str, Any], margin: float | None, can_recommend: bool) -> dict[str, Any] | None:
    if not s.quotes:
        return None
    prices = sorted(q.price for q in s.quotes)
    best = max(s.quotes, key=lambda q: q.price)
    med = statistics.median(prices)
    p = s.model_prob or s.fair_prob
    price = best.price
    implied = 1 / price
    ev = p * price - 1
    ev_tax = p * price * (1 - TAX) - 1
    hist = None
    lb = (buckets.get(league) or {}).get("buckets") or []
    for b in lb:
        if b["from"] <= med < b["to"]:
            hist = b | {"league": LEAGUE_BY_KEY[league].name if league in LEAGUE_BY_KEY else league, "matches": (buckets.get(league) or {}).get("matches"), "source": (buckets.get(league) or {}).get("source")}
            break
    move = None
    if len(s.history) >= 2:
        (t0, p0), (_, p1) = s.history[0], s.history[-1]
        move = {"first": p0, "last": p1, "changePct": p1 / p0 - 1, "since": t0.strftime("%Y-%m-%dT%H:%M:%SZ")}
    series = {
        "n10AllWin": p**10,
        "n10ExpectedLosses": 10 * (1 - p),
        "n10InLoss": _binom_loss_prob(10, p, price),
        "n50InLoss": _binom_loss_prob(50, p, price),
    }
    acca = {"legs": 3, "price": price**3, "prob": p**3, "evTaxed": (p * price) ** 3 * (1 - TAX) - 1}
    return {
        "selectionId": None,  # filled by the caller (needs the event id)
        "label": s.label,
        "key": s.key,
        "price": price,
        "bookmaker": best.bookmaker,
        "worstPrice": prices[0],
        "medianPrice": med,
        "books": len(prices),
        "implied": implied,
        "fairProb": s.fair_prob,
        "finalProb": p,
        "rawModelProb": s.raw_model_prob,
        "marketMargin": margin,
        "marginInPrice": implied - s.fair_prob,
        "ev": ev,
        "evTaxed": ev_tax,
        "breakEven": implied,
        "breakEvenTaxed": 1 / (price * (1 - TAX)),
        "minPriceTaxed": 1 / (p * (1 - TAX)) if p > 0 else None,
        "loseProb": 1 - p,
        "oneInN": (1 / (1 - p)) if p < 1 else None,
        "per100": {"expected": 100 * ev_tax, "win": 100 * (price * (1 - TAX) - 1), "lose": -100.0, "sd": 100 * price * (1 - TAX) * math.sqrt(max(p * (1 - p), 0))},
        "series": series,
        "acca": acca,
        "movement": move,
        "history": hist,
        "canRecommend": can_recommend,
    }


def prob_text(x: float) -> str:
    return "ponad 99%" if x > 0.99 else "poniżej 1%" if x < 0.01 else pct(x)


def days_pl(n: float) -> str:
    k = int(round(n))
    return f"{k} dzień" if k == 1 else f"{k} dni"


def games_pl(k: int) -> str:
    return f"{k} mecz" if k == 1 else f"{k} mecze" if 2 <= k % 10 <= 4 and not 12 <= k % 100 <= 14 else f"{k} meczów"


def history_judgement(h: dict[str, Any]) -> str:
    """Were such prices too short (favourites overrated), fair, or too long — beyond chance?"""
    if h["winRateHigh"] < h["fair"]:
        return "Takie kursy były zbyt niskie: faworyci wygrywali rzadziej, niż wynika z kursu nawet bez marży — tu jest realna pułapka."
    if h["winRateLow"] > h["fair"]:
        return "Takie kursy były raczej za wysokie (faworyci wygrywali częściej) — ale po podatku i tak zwykle bez zysku."
    if h["winRate"] < h["fair"] - 0.015:
        return "Wygrywały nieco rzadziej, niż zakłada kurs bez marży, ale różnica mieści się w przypadku. Pułapką jest głównie marża i podatek."
    return "Wycena była trafna — pułapką nie jest „ustawiona” szansa, tylko marża i podatek."


def verdict(si: dict[str, Any], fav: bool, facts: dict[str, Any], side_is_home: bool | None, is_fb: bool) -> dict[str, Any]:
    """Plain-language verdict for one selection."""
    pts: list[str] = []
    price, p = si["price"], si["finalProb"]
    if si["evTaxed"] >= 0 and si["ev"] >= 0.02 and si["canRecommend"]:
        level, head = "value", "Kurs wyższy od uczciwego — po podatku nadal na plus"
    elif si["evTaxed"] >= 0:
        level, head = "neutral", "Kurs blisko uczciwego; przewagi nie potwierdził backtest"
    elif price < 1.6:
        level, head = "avoid", "Kurs uczciwy, ale nieopłacalny — „pewniak” przegrywa przez marżę i podatek"
    else:
        level, head = "avoid", "Nieopłacalny: kurs poniżej uczciwego po podatku"
    if si["marginInPrice"] >= 0:
        pts.append(
            f"Kurs {pl(price, 2)} zakłada {pct(si['implied'], 1)} szans; rynek bez marży ocenia je na {pct(si['fairProb'], 1)}, "
            f"więc w samym kursie bukmacher zaszył {pl(100 * si['marginInPrice'], 1)} p.p. marży."
        )
    else:
        pts.append(
            f"Kurs {pl(price, 2)} zakłada {pct(si['implied'], 1)} szans, mniej niż rynek bez marży ({pct(si['fairProb'], 1)}): "
            f"ten bukmacher płaci o {pl(-100 * si['marginInPrice'], 1)} p.p. więcej niż uczciwie — sprawdź, czy polski bukmacher da podobny kurs."
        )
    pts.append(
        f"Żeby wyjść na zero po 12% podatku, ta selekcja musiałaby wygrywać {pct(si['breakEvenTaxed'], 1)} razy, a realnie wygrywa ok. {pct(p, 1)}. "
        f"Na każde 100 zł średnio {'zyskujesz' if si['per100']['expected'] >= 0 else 'tracisz'} {pl(abs(si['per100']['expected']), 1)} zł."
    )
    if si["minPriceTaxed"]:
        pts.append(f"Opłaca się dopiero od kursu {pl(si['minPriceTaxed'], 2)} u polskiego bukmachera (z podatkiem).")
    h = si.get("history")
    if h:
        pts.append(
            f"Historia ({h['league']}, {h['n']} selekcji z kursem {pl(h['from'], 2)}–{pl(h['to'], 2)}): wygrały {pct(h['winRate'], 1)} "
            f"(95%: {pct(h['winRateLow'])}–{pct(h['winRateHigh'])}); kurs zakładał {pct(h['implied'], 1)}, a po odjęciu marży {pct(h['fair'], 1)}. "
            + history_judgement(h)
            + f" Obstawianie wszystkich: {spct(h['roiAvg'])} przy kursie średnim, {spct(h['roiTaxed'])} po podatku."
        )
    if fav and price < 1.6:
        pts.append(
            f"Ryzyko: przegrywa średnio 1 na {pl(si['oneInN'], 1)} takich zakładów. Szansa, że 10 kolejnych wejdzie: {pct(si['series']['n10AllWin'])}; "
            f"po 10 zakładach jesteś na minusie z prawdopodobieństwem {prob_text(si['series']['n10InLoss'])}, po 50 — {prob_text(si['series']['n50InLoss'])}."
        )
        ac = si["acca"]
        pts.append(f"Kupon z 3 takich „pewniaków”: kurs {pl(ac['price'], 2)}, szansa {pct(ac['prob'])}, oczekiwany wynik po podatku {spct(ac['evTaxed'])} — marża mnoży się z każdym zdarzeniem.")
    mv = si.get("movement")
    if mv and abs(mv["changePct"]) >= 0.03:
        pts.append(f"Kurs {'spadł' if mv['changePct'] < 0 else 'wzrósł'} z {pl(mv['first'], 2)} do {pl(mv['last'], 2)} ({spct(mv['changePct'])}) — "
                   + ("rynek dokłada pieniądze na tę stronę (często informacja o składach)." if mv["changePct"] < 0 else "rynek odchodzi od tej strony."))
    return {"level": level, "headline": head, "points": pts}


def why_text(fav_label: str, fav_price: float, fav_home: bool, facts: dict[str, Any], is_fb: bool) -> str:
    """Why is the favourite priced short (also when it lost recently)?"""
    parts = []
    rank = facts.get("rank")
    losses = facts.get("losses")
    fi = 0 if fav_home else 1
    if rank:
        mine, theirs = (rank[0], rank[1]) if fav_home else (rank[1], rank[0])
        parts.append(f"w ocenie z całego okresu to {mine}. drużyna, rywal — {theirs}. (na {rank[2]})")
    if losses and losses[fi] >= 2:
        opp = facts.get("opp_rank")
        tight = facts.get("tight")
        extra = []
        if opp:
            extra.append(f"rywale w tych meczach to średnio {pl(opp[fi])}. drużyna ligi")
        if tight and tight[fi]:
            extra.append(f"{tight[fi]} z porażek na styk")
        parts.append(f"{losses[fi]} porażki w ostatnich {FORM_N} meczach rynek traktuje jako krótką serię" + (f" ({', '.join(extra)})" if extra else ""))
    if fav_home:
        parts.append("gra u siebie")
    fat = facts.get("fatigue")
    if fat and fat[1 - fi] > fat[fi]:
        parts.append("rywal jest bardziej zmęczony terminarzem")
    base = f"Kurs {pl(fav_price, 2)} na „{fav_label}” wynika głównie z tego, że " + "; ".join(parts) + "." if parts else f"Kurs {pl(fav_price, 2)} na „{fav_label}” odzwierciedla ocenę rynku."
    return (
        base
        + " Bukmacherzy ustalają kursy na podstawie siły z wielu miesięcy, składów i kontuzji oraz pieniędzy graczy, a nie samej serii ostatnich wyników — "
        "dlatego dwie drużyny w słabej formie mogą mieć bardzo różne kursy. Model nie zna składów: jeśli kurs jest niższy, niż sugerują dane, często stoi za tym powrót kluczowych zawodników lub osłabienie rywala."
    )


def build(conn: sqlite3.Connection, a: EventAnalysis, model: DixonColes | Ratings | None, buckets: dict[str, Any]) -> dict[str, Any] | None:
    ev = a.event
    h2h = next((m for m in a.markets if m.market == "h2h"), None)
    if h2h is None or not any(s.quotes for s in h2h.selections):
        return None
    is_fb = ev["sport"] == "football"
    st = strengths(model)
    facs, facts = factors(conn, a, model, st)
    can = a.params.can_recommend("h2h") if a.params else False
    sels = []
    priced = [s for s in h2h.selections if s.quotes]
    fav = min(priced, key=lambda s: max(q.price for q in s.quotes))
    for s in priced:
        si = selection_insight(s, ev["league_key"], buckets, h2h.margin, can and not a.market_only)
        if si is None:
            continue
        si["selectionId"] = f"{ev['id']}:{h2h.market}:{s.key}:{s.line}"
        side_home = True if s.key == "home" else False if s.key == "away" else None
        si["verdict"] = verdict(si, s is fav, facts, side_home, is_fb)
        sels.append(si)
    fav_price = max(q.price for q in fav.quotes)
    return _round({
        "favouriteSelectionId": f"{ev['id']}:{h2h.market}:{fav.key}:{fav.line}",
        "why": why_text(fav.label, fav_price, fav.key == "home", facts, is_fb) if fav.key != "draw" else "",
        "factors": facs,
        "selections": sels,
        "modelNote": "Prawdopodobieństwo = rynek bez marży" + (" połączony z modelem" if (a.params and a.params.weight('h2h') > 0) else "") + " (backtest: rynek prognozuje lepiej niż sam model).",
    })


def _round(x: Any) -> Any:
    """Keep the published JSON small (the phone caches it)."""
    if isinstance(x, float):
        return round(x, 4)
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v) for v in x]
    return x
