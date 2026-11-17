"""Glue: fit models from stored results, price upcoming events, keep the recommendation lifecycle, settle."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .config import HORIZON_DAYS, LEAGUE_BY_KEY, MAX_ODDS_AGE_H, previous_season
from .db import dumps
from .engine.evaluate import Candidate, Context, Market, Quote, Selection, fmt_pct, price_market
from .engine.odds import closing_line_value
from .models.basketball import Game, Ratings
from .models.football import DixonColes, Match, outcome_probs, total_over
from .providers.http import iso

MODEL_VERSION = {"football": "dixon-coles-v0", "basketball": "ratings-v0"}


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def fmt_line(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def signed(x: float) -> str:
    return ("+" if x > 0 else "−") + fmt_line(abs(x))


# ---------------- models ----------------

def fit_models(conn: sqlite3.Connection, now: datetime) -> dict[str, DixonColes | Ratings]:
    models: dict[str, DixonColes | Ratings] = {}
    for key, lg in LEAGUE_BY_KEY.items():
        row = conn.execute("SELECT season FROM leagues WHERE key = ?", (key,)).fetchone()
        if not row:
            continue
        seasons = (row["season"], previous_season(lg.sport, row["season"]))
        rows = conn.execute(
            f"""SELECT home_team_id, away_team_id, home_score, away_score, kickoff FROM events
                WHERE league_key = ? AND season IN (?, ?) AND status = 'finished'
                AND home_score IS NOT NULL AND away_score IS NOT NULL AND kickoff < ?""",
            (key, *seasons, iso(now)),
        ).fetchall()
        age = lambda r: (now - parse(r["kickoff"])).total_seconds() / 86400  # noqa: E731
        if lg.sport == "football":
            models[key] = DixonColes.fit([Match(r["home_team_id"], r["away_team_id"], r["home_score"], r["away_score"], age(r)) for r in rows])
        else:
            models[key] = Ratings.fit([Game(r["home_team_id"], r["away_team_id"], r["home_score"], r["away_score"], age(r)) for r in rows])
    return models


# ---------------- odds loading ----------------

def latest_quotes(conn: sqlite3.Connection, event_id: str) -> tuple[dict[tuple, list[Quote]], dict[tuple, list[tuple[datetime, float]]]]:
    rows = conn.execute(
        "SELECT bookmaker, market, selection, line, price, captured_at FROM odds_snapshots WHERE event_id = ? ORDER BY captured_at",
        (event_id,),
    ).fetchall()
    latest: dict[tuple, dict[str, Quote]] = {}
    best_by_time: dict[tuple, dict[str, float]] = {}
    for r in rows:
        k = (r["market"], r["selection"], r["line"])
        latest.setdefault(k, {})[r["bookmaker"]] = Quote(r["bookmaker"], r["price"], parse(r["captured_at"]))
        t = best_by_time.setdefault(k, {})
        t[r["captured_at"]] = max(t.get(r["captured_at"], 0.0), r["price"])
    quotes = {k: list(v.values()) for k, v in latest.items()}
    history = {k: [(parse(ts), p) for ts, p in sorted(v.items())] for k, v in best_by_time.items()}
    return quotes, history


# ---------------- per-event analysis ----------------

@dataclass
class EventAnalysis:
    event: sqlite3.Row
    markets: list[Market] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    model_note: str = ""
    lam_mu: tuple[float, float] | None = None
    margin_total: tuple[float, float] | None = None
    odds_fresh: bool = False
    odds_updated: datetime | None = None
    completeness: float = 0.0
    known: bool = False


def analyse_event(conn: sqlite3.Connection, ev: sqlite3.Row, model: DixonColes | Ratings | None, now: datetime) -> EventAnalysis:
    a = EventAnalysis(event=ev)
    if model is None:
        return a
    h, w = ev["home_team_id"], ev["away_team_id"]
    hn, an = ev["home_name"], ev["away_name"]
    quotes, history = latest_quotes(conn, ev["id"])
    times = [q.captured_at for qs in quotes.values() for q in qs]
    a.odds_updated = max(times) if times else None
    a.odds_fresh = bool(a.odds_updated and now - a.odds_updated <= timedelta(hours=MAX_ODDS_AGE_H))
    a.known = model.known(h) and model.known(w)
    injuries_fetched = conn.execute("SELECT 1 FROM injuries WHERE league_key = ? AND fetched_at >= ? LIMIT 1", (ev["league_key"], iso(now - timedelta(hours=36)))).fetchone() is not None
    n_min = min(model.n_eff.get(h, 0.0), model.n_eff.get(w, 0.0))
    a.completeness = round(
        (1.0 if a.odds_fresh else 0.0) * 0.35
        + (1.0 if injuries_fetched else 0.0) * 0.2
        + min(1.0, n_min / 15) * 0.35
        + 0.1,  # fixtures/results always present when we get here
        3,
    )
    ctx = Context(now=now, kickoff=parse(ev["kickoff"]), completeness=a.completeness, both_teams_known=a.known)
    is_fb = ev["sport"] == "football"

    def sel(key: str, label: str, line: float | None, p: float, mkey: str) -> Selection:
        qk = (mkey, key, line)
        return Selection(key, label, line, quotes.get(qk, []), p, history=history.get(qk, []))

    if is_fb:
        assert isinstance(model, DixonColes)
        m = model.score_matrix(h, w)
        a.lam_mu = model.rates(h, w)
        hw = lambda p: model.half_width(p, h, w)  # noqa: E731
        o = outcome_probs(m)
        a.markets.append(Market("h2h", "1X2", None, [sel("home", f"Wygrana {hn}", None, o["home"], "h2h"), sel("draw", "Remis", None, o["draw"], "h2h"), sel("away", f"Wygrana {an}", None, o["away"], "h2h")]))
        for line in sorted({k[2] for k in quotes if k[0] == "totals" and k[2] is not None}):
            p = total_over(m, line)
            a.markets.append(Market("totals", f"Gole: powyżej/poniżej {fmt_line(line)}", line, [sel("over", f"Powyżej {fmt_line(line)} gola", line, p, "totals"), sel("under", f"Poniżej {fmt_line(line)} gola", line, 1 - p, "totals")]))
    else:
        assert isinstance(model, Ratings)
        a.margin_total = model.predict(h, w)
        hw = lambda p: model.half_width(p, h, w)  # noqa: E731
        p = model.p_home_win(h, w)
        a.markets.append(Market("h2h", "Moneyline", None, [sel("home", f"Wygrana {hn}", None, p, "h2h"), sel("away", f"Wygrana {an}", None, 1 - p, "h2h")]))
        for line in sorted({k[2] for k in quotes if k[0] == "spreads" and k[1] == "home" and k[2] is not None}):
            pc = model.p_home_cover(h, w, line)
            a.markets.append(Market("spreads", f"Handicap {signed(line)}", line, [sel("home", f"{hn} {signed(line)}", line, pc, "spreads"), Selection("away", f"{an} {signed(-line)}", -line, quotes.get(("spreads", "away", -line), []), 1 - pc, history=history.get(("spreads", "away", -line), []))]))
        for line in sorted({k[2] for k in quotes if k[0] == "totals" and k[2] is not None}):
            po = model.p_over(h, w, line)
            a.markets.append(Market("totals", f"Punkty: powyżej/poniżej {fmt_line(line)}", line, [sel("over", f"Powyżej {fmt_line(line)} pkt", line, po, "totals"), sel("under", f"Poniżej {fmt_line(line)} pkt", line, 1 - po, "totals")]))

    for mk in a.markets:
        a.candidates.extend(price_market(mk, hw, ctx))
    a.candidates.sort(key=lambda c: (c.quality, c.ev), reverse=True)
    a.candidates = a.candidates[:2]
    return a


# ---------------- reasons ----------------

def team_form(conn: sqlite3.Connection, team_id: str, before: str, n: int = 8) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT e.*, h.name AS home_name, w.name AS away_name FROM events e
           JOIN teams h ON h.id = e.home_team_id JOIN teams w ON w.id = e.away_team_id
           WHERE (e.home_team_id = ? OR e.away_team_id = ?) AND e.status = 'finished' AND e.kickoff < ?
           ORDER BY e.kickoff DESC LIMIT ?""",
        (team_id, team_id, before, n),
    ).fetchall()


def reasons(conn: sqlite3.Connection, a: EventAnalysis, c: Candidate) -> tuple[list[str], list[str]]:
    ev = a.event
    pro, con = [], []
    if a.lam_mu:
        lam, mu = a.lam_mu
        pro.append(f"Model Dixon–Coles: oczekiwane bramki {lam:.2f} – {mu:.2f} (suma {lam + mu:.2f})".replace(".", ","))
        for tid, name in ((ev["home_team_id"], ev["home_short"]), (ev["away_team_id"], ev["away_short"])):
            f = team_form(conn, tid, ev["kickoff"])
            if f:
                gf = sum(r["home_score"] if r["home_team_id"] == tid else r["away_score"] for r in f) / len(f)
                ga = sum(r["away_score"] if r["home_team_id"] == tid else r["home_score"] for r in f) / len(f)
                pro.append(f"{name}: średnio {gf:.2f} strzelone i {ga:.2f} stracone gola w ostatnich {len(f)} meczach".replace(".", ","))
    if a.margin_total:
        m, t = a.margin_total
        pro.append(f"Model ratingowy: oczekiwana różnica {('+' if m >= 0 else '−')}{abs(m):.1f} pkt dla {ev['home_short']}, suma {t:.1f} pkt".replace(".", ","))
    title = conn.execute("SELECT title FROM bookmakers WHERE key = ?", (c.best.bookmaker,)).fetchone() if _has_table(conn, "bookmakers") else None
    pro.append(f"Kurs {c.best.price:.2f} ({title['title'] if title else c.best.bookmaker}) vs kurs godziwy {1 / c.sel.model_prob:.2f}")
    pro.append(f"Model bez korekty rynkowej: {fmt_pct(c.sel.raw_model_prob)}; rynek bez marży: {fmt_pct(c.sel.fair_prob)}")
    if c.sel.prob_low > c.implied:
        pro.append(f"Cały przedział ({fmt_pct(c.sel.prob_low, 0)}–{fmt_pct(c.sel.prob_high, 0)}) powyżej p. implikowanego {fmt_pct(c.implied)}")
    else:
        con.append(f"Przedział niepewności {fmt_pct(c.sel.prob_low, 0)}–{fmt_pct(c.sel.prob_high, 0)} obejmuje p. implikowane {fmt_pct(c.implied)}")
    con.append("Składy niepotwierdzone w chwili analizy (aktualizacja 1–2 razy dziennie)")
    if len(c.sel.history) >= 2 and c.sel.history[-1][1] / c.sel.history[0][1] - 1 < -0.03:
        con.append(f"Kurs spadł o {fmt_pct(1 - c.sel.history[-1][1] / c.sel.history[0][1])} od pierwszego odczytu — rynek mógł już uwzględnić część informacji")
    inj = conn.execute(
        "SELECT COUNT(*) AS n FROM injuries WHERE team_id IN (?, ?) AND (fixture_event_id = ? OR fixture_event_id IS NULL)",
        (ev["home_team_id"], ev["away_team_id"], ev["id"]),
    ).fetchone()["n"]
    if ev["sport"] == "football" and inj:
        con.append(f"Zgłoszone absencje ({inj}) nie są jeszcze ilościowo uwzględniane w modelu v0")
    if ev["sport"] == "basketball":
        con.append("Brak danych o kontuzjach w darmowym źródle — sprawdź raport kontuzji przed meczem")
    if c.best.price > 2.6:
        con.append("Wysoki kurs = duża wariancja wyniku pojedynczego zakładu")
    return pro, con


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


# ---------------- lifecycle ----------------

def sync_recommendations(conn: sqlite3.Connection, a: EventAnalysis, now: datetime) -> dict[str, int]:
    ev = a.event
    stats = {"new": 0, "updated": 0, "withdrawn": 0}
    if not a.odds_fresh or parse(ev["kickoff"]) <= now:
        return stats  # frozen: stale odds or already started — neither create nor withdraw
    existing = {r["id"]: r for r in conn.execute("SELECT * FROM recommendations WHERE event_id = ?", (ev["id"],))}
    keep: set[str] = set()
    for c in a.candidates:
        rid = f"{ev['id']}:{c.market.market}:{c.sel.key}:{c.sel.line}"
        keep.add(rid)
        row = existing.get(rid)
        if row is None:
            pro, con = reasons(conn, a, c)
            conn.execute(
                """INSERT INTO recommendations(id, event_id, market, selection, line, label, bookmaker, price, current_price, model_prob, prob_low, prob_high,
                   implied_prob, fair_prob, ev, quality, risk, reasons_for, reasons_against, model_version, generated_at, updated_at, status, result)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'active','pending')""",
                (rid, ev["id"], c.market.market, c.sel.key, c.sel.line, c.sel.label, c.best.bookmaker, c.best.price, c.best.price, c.sel.model_prob, c.sel.prob_low, c.sel.prob_high,
                 c.implied, c.sel.fair_prob, c.ev, c.quality, c.risk, dumps(pro), dumps(con), MODEL_VERSION[ev["sport"]], iso(now), iso(now)),
            )
            stats["new"] += 1
        elif row["status"] == "active":
            conn.execute(
                "UPDATE recommendations SET current_price = ?, updated_at = ? WHERE id = ?",
                (c.best.price, iso(now), rid),
            )
            stats["updated"] += 1
    for rid, row in existing.items():
        if row["status"] == "active" and rid not in keep:
            reason = withdraw_reason(a, row)
            conn.execute("UPDATE recommendations SET status = 'withdrawn', withdraw_reason = ?, updated_at = ?, result = NULL WHERE id = ?", (reason, iso(now), rid))
            stats["withdrawn"] += 1
    conn.commit()
    return stats


def withdraw_reason(a: EventAnalysis, row: sqlite3.Row) -> str:
    for mk in a.markets:
        for s in mk.selections:
            if mk.market == row["market"] and s.key == row["selection"] and s.line == row["line"] and s.best:
                if s.best.price < row["price"]:
                    return f"Kurs spadł z {row['price']:.2f} do {s.best.price:.2f} — przewaga poniżej progu."
                ev = s.model_prob * s.best.price - 1
                return f"Po aktualizacji danych EV wynosi {fmt_pct(ev)} — poniżej progu jakości."
    return "Rynek zniknął z oferty lub dane przestały być aktualne."


# ---------------- settlement ----------------

def settle(conn: sqlite3.Connection, now: datetime) -> int:
    rows = conn.execute(
        """SELECT r.*, e.status AS ev_status, e.home_score, e.away_score, e.kickoff FROM recommendations r
           JOIN events e ON e.id = r.event_id
           WHERE r.status = 'active' AND e.status IN ('finished', 'cancelled', 'postponed') AND e.kickoff < ?""",
        (iso(now),),
    ).fetchall()
    n = 0
    for r in rows:
        if r["ev_status"] == "postponed" and now - parse(r["kickoff"]) < timedelta(days=2):
            continue  # wait: may be played within bookmaker rules window
        if r["ev_status"] != "finished" or r["home_score"] is None:
            result, profit = "void", 0.0
        else:
            won = outcome_won(r["market"], r["selection"], r["line"], r["home_score"], r["away_score"])
            result, profit = ("won", r["price"] - 1) if won else ("lost", -1.0)
        close = conn.execute(
            """SELECT price FROM odds_snapshots WHERE event_id = ? AND bookmaker = ? AND market = ? AND selection = ?
               AND ((line IS NULL AND ? IS NULL) OR line = ?) AND captured_at <= ? ORDER BY captured_at DESC LIMIT 1""",
            (r["event_id"], r["bookmaker"], r["market"], r["selection"], r["line"], r["line"], r["kickoff"]),
        ).fetchone()
        conn.execute(
            "UPDATE recommendations SET status = 'settled', result = ?, profit = ?, closing_price = ?, settled_at = ? WHERE id = ?",
            (result, profit, close["price"] if close else None, iso(now), r["id"]),
        )
        n += 1
    conn.commit()
    return n


def outcome_won(market: str, selection: str, line: float | None, hs: int, as_: int) -> bool:
    if market == "h2h":
        return {"home": hs > as_, "draw": hs == as_, "away": hs < as_}[selection]
    if market == "totals":
        return (hs + as_ > line) if selection == "over" else (hs + as_ < line)
    if market == "spreads":
        return (hs + line > as_) if selection == "home" else (as_ + line > hs)
    raise ValueError(f"Unknown market {market}")


def upcoming_events(conn: sqlite3.Connection, now: datetime) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT e.*, h.name AS home_name, w.name AS away_name, h.short_name AS home_short, w.short_name AS away_short,
                  h.logo_url AS home_logo, w.logo_url AS away_logo
           FROM events e JOIN teams h ON h.id = e.home_team_id JOIN teams w ON w.id = e.away_team_id
           WHERE e.kickoff BETWEEN ? AND ? AND e.status IN ('scheduled', 'live')
           ORDER BY e.kickoff""",
        (iso(now - timedelta(hours=3)), iso(now + timedelta(days=HORIZON_DAYS))),
    ).fetchall()


def clv(row: sqlite3.Row) -> float | None:
    return closing_line_value(row["price"], row["closing_price"]) if row["closing_price"] else None

