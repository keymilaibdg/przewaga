"""Export JSON files consumed by the PWA. Shapes mirror frontend/src/types/domain.ts."""
from __future__ import annotations

import colorsys
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .analysis import EventAnalysis, clv, parse, team_form
from .config import LEAGUE_BY_KEY, MAX_ODDS_AGE_H
from .engine.evaluate import Market
from .providers.http import iso

NO_BET = "Brak zakładów spełniających obecnie kryteria jakości. Nie rekomendujemy obstawiania tego wydarzenia."

MARKET_TYPE = {
    ("football", "h2h"): "1X2",
    ("football", "totals"): "TOTAL_GOALS",
    ("basketball", "h2h"): "MONEYLINE",
    ("basketball", "totals"): "TOTAL_POINTS",
    ("basketball", "spreads"): "SPREAD",
}

UNAVAILABLE = {
    "football": [
        ("DOUBLE_CHANCE", "Podwójna szansa"),
        ("DRAW_NO_BET", "Draw No Bet"),
        ("BTTS", "Obie drużyny strzelą"),
        ("ASIAN_HANDICAP", "Handicap azjatycki"),
        ("TEAM_TOTAL", "Gole drużyny"),
        ("CORNERS", "Rzuty rożne"),
        ("CARDS", "Kartki"),
    ],
    "basketball": [("TEAM_POINTS", "Punkty drużyny"), ("PLAYER_PROPS", "Statystyki zawodników")],
}
UNAVAILABLE_REASON = "Niedostępny: rynek nie jest pobierany w darmowym planie kursów (każdy dodatkowy rynek zużywa miesięczny limit). Nie wyceniamy rynków bez kursów."


def pct(x: float) -> str:
    return f"{x * 100:.1f}%".replace(".", ",")


def team_colors(name: str) -> list[str]:
    h = int(hashlib.sha1(name.encode()).hexdigest()[:6], 16) / 0xFFFFFF
    r, g, b = colorsys.hls_to_rgb(h, 0.42, 0.55)
    return ["#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255)), "#ffffff"]


def team_json(tid: str, name: str, short: str, logo: str | None) -> dict[str, Any]:
    return {"id": tid, "name": name, "shortName": short or name[:3].upper(), "logoUrl": logo, "colors": team_colors(name)}


def bookmaker_titles(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        return {r["key"]: r["title"] for r in conn.execute("SELECT key, title FROM bookmakers")}
    except sqlite3.OperationalError:
        return {}


def market_json(sport: str, mk: Market, event_id: str) -> dict[str, Any]:
    mtype = MARKET_TYPE[(sport, mk.market)]
    return {
        "market": mtype,
        "name": mk.name,
        "margin": mk.margin,
        "available": True,
        "verdict": mk.verdict,
        "selections": [
            {
                "id": f"{event_id}:{mk.market}:{s.key}:{s.line}",
                "market": mtype,
                "label": s.label,
                "line": s.line,
                "quotes": sorted(
                    [{"bookmaker": q.bookmaker, "price": q.price, "updatedAt": iso(q.captured_at)} for q in s.quotes],
                    key=lambda q: -q["price"],
                ),
                "modelProb": s.model_prob,
                "probLow": s.prob_low,
                "probHigh": s.prob_high,
                "fairProb": s.fair_prob,
                "priceHistory": [{"at": iso(t), "price": p} for t, p in s.history] or ([{"at": iso(s.best.captured_at), "price": s.best.price}] if s.best else []),
            }
            for s in mk.selections
            if s.quotes
        ],
    }


def rec_json(r: sqlite3.Row, sport: str) -> dict[str, Any]:
    return {
        "id": r["id"],
        "eventId": r["event_id"],
        "selectionId": f"{r['event_id']}:{r['market']}:{r['selection']}:{r['line']}",
        "market": MARKET_TYPE[(sport, r["market"])],
        "label": r["label"],
        "bookmaker": r["bookmaker"],
        "price": r["price"],
        "modelProb": r["model_prob"],
        "probLow": r["prob_low"],
        "probHigh": r["prob_high"],
        "impliedProb": r["implied_prob"],
        "fairProb": r["fair_prob"],
        "ev": r["ev"],
        "quality": r["quality"],
        "risk": r["risk"],
        "reasonsFor": json.loads(r["reasons_for"]),
        "reasonsAgainst": json.loads(r["reasons_against"]),
        "generatedAt": r["generated_at"],
        "updatedAt": r["updated_at"],
        "status": "withdrawn" if r["status"] == "withdrawn" else "active",
        **({"withdrawReason": r["withdraw_reason"]} if r["withdraw_reason"] else {}),
    }


def form_json(rows: list[sqlite3.Row], tid: str) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        home = r["home_team_id"] == tid
        s, c = (r["home_score"], r["away_score"]) if home else (r["away_score"], r["home_score"])
        out.append({"date": r["kickoff"], "opponent": r["away_name"] if home else r["home_name"], "home": home, "scored": s, "conceded": c, "result": "W" if s > c else "D" if s == c else "L"})
    return out


def stats_json(sport: str, fh: list[dict], fa: list[dict], ea: EventAnalysis) -> list[dict[str, Any]]:
    def avg(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    def share(f: list[dict], pred) -> float | None:
        return sum(1 for x in f if pred(x)) / len(f) if f else None

    gf = lambda f: avg([x["scored"] for x in f])  # noqa: E731
    ga = lambda f: avg([x["conceded"] for x in f])  # noqa: E731
    src = "API-SPORTS"
    if sport == "football":
        lam_mu = ea.lam_mu or (None, None)
        return [
            {"key": "gf", "label": "Gole strzelone / mecz", "home": gf(fh), "away": gf(fa), "higherIsBetter": True, "format": "dec2", "source": src},
            {"key": "ga", "label": "Gole stracone / mecz", "home": ga(fh), "away": ga(fa), "higherIsBetter": False, "format": "dec2", "source": src},
            {"key": "gf_split", "label": "Gole u siebie / na wyjeździe", "home": avg([x["scored"] for x in fh if x["home"]]), "away": avg([x["scored"] for x in fa if not x["home"]]), "higherIsBetter": True, "format": "dec2", "source": src},
            {"key": "exp", "label": "Oczekiwane gole (model)", "home": lam_mu[0], "away": lam_mu[1], "higherIsBetter": True, "format": "dec2", "source": "model"},
            {"key": "xg", "label": "xG / mecz", "home": None, "away": None, "higherIsBetter": True, "format": "dec2", "source": None},
            {"key": "o25", "label": "Mecze powyżej 2,5 gola", "home": share(fh, lambda x: x["scored"] + x["conceded"] > 2.5), "away": share(fa, lambda x: x["scored"] + x["conceded"] > 2.5), "higherIsBetter": True, "format": "pct", "source": src},
            {"key": "btts", "label": "Mecze BTTS", "home": share(fh, lambda x: x["scored"] > 0 and x["conceded"] > 0), "away": share(fa, lambda x: x["scored"] > 0 and x["conceded"] > 0), "higherIsBetter": True, "format": "pct", "source": src},
        ]
    net = lambda f: avg([x["scored"] - x["conceded"] for x in f])  # noqa: E731
    return [
        {"key": "ppg", "label": "Punkty zdobyte / mecz", "home": gf(fh), "away": gf(fa), "higherIsBetter": True, "format": "dec1", "source": src},
        {"key": "opp", "label": "Punkty stracone / mecz", "home": ga(fh), "away": ga(fa), "higherIsBetter": False, "format": "dec1", "source": src},
        {"key": "net", "label": "Bilans punktowy / mecz", "home": net(fh), "away": net(fa), "higherIsBetter": True, "format": "dec1", "source": src},
        {"key": "ortg", "label": "Offensive Rating", "home": None, "away": None, "higherIsBetter": True, "format": "dec1", "source": None},
        {"key": "drtg", "label": "Defensive Rating", "home": None, "away": None, "higherIsBetter": False, "format": "dec1", "source": None},
        {"key": "pace", "label": "Pace", "home": None, "away": None, "higherIsBetter": True, "format": "dec1", "source": None},
    ]


def absences_json(conn: sqlite3.Connection, ev: sqlite3.Row, now: datetime) -> list[dict[str, Any]] | None:
    fetched = conn.execute("SELECT 1 FROM injuries WHERE league_key = ? AND fetched_at >= ? LIMIT 1", (ev["league_key"], iso(now - timedelta(hours=36)))).fetchone()
    if ev["sport"] != "football" or not fetched:
        return None
    rows = conn.execute(
        "SELECT * FROM injuries WHERE team_id IN (?, ?) AND (fixture_event_id = ? OR fixture_event_id IS NULL)",
        (ev["home_team_id"], ev["away_team_id"], ev["id"]),
    ).fetchall()
    kind = lambda r: "doubtful" if (r["kind"] or "").lower().startswith("question") else ("suspension" if "suspen" in (r["reason"] or "").lower() or "card" in (r["reason"] or "").lower() else "injury")  # noqa: E731
    return [
        {"player": r["player"], "team": "home" if r["team_id"] == ev["home_team_id"] else "away", "reason": kind(r), "importance": "regular", "note": r["reason"]}
        for r in rows
    ]


def h2h_json(conn: sqlite3.Connection, ev: sqlite3.Row) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT e.kickoff, h.name AS hn, w.name AS an, e.home_score, e.away_score, e.league_key FROM events e
           JOIN teams h ON h.id = e.home_team_id JOIN teams w ON w.id = e.away_team_id
           WHERE e.status = 'finished' AND ((e.home_team_id = ? AND e.away_team_id = ?) OR (e.home_team_id = ? AND e.away_team_id = ?))
           ORDER BY e.kickoff DESC LIMIT 5""",
        (ev["home_team_id"], ev["away_team_id"], ev["away_team_id"], ev["home_team_id"]),
    ).fetchall()
    return [{"date": r["kickoff"], "homeTeam": r["hn"], "awayTeam": r["an"], "homeScore": r["home_score"], "awayScore": r["away_score"], "competition": LEAGUE_BY_KEY[r["league_key"]].name} for r in rows]


def freshness(ts: datetime | None, now: datetime, limit_h: float) -> str:
    if ts is None:
        return "missing"
    age = (now - ts).total_seconds() / 3600
    return "fresh" if age <= limit_h else "aging" if age <= limit_h * 2 else "stale"


def event_json(conn: sqlite3.Connection, ea: EventAnalysis, now: datetime) -> dict[str, Any]:
    ev = ea.event
    lg = LEAGUE_BY_KEY[ev["league_key"]]
    fh = form_json(team_form(conn, ev["home_team_id"], ev["kickoff"]), ev["home_team_id"])
    fa = form_json(team_form(conn, ev["away_team_id"], ev["kickoff"]), ev["away_team_id"])
    recs = conn.execute("SELECT * FROM recommendations WHERE event_id = ? AND status IN ('active','withdrawn') ORDER BY quality DESC", (ev["id"],)).fetchall()
    absences = absences_json(conn, ev, now)
    flags: list[str] = []
    if not ea.odds_fresh:
        flags.append("Kursy nieaktualne — rekomendacje wstrzymane" if ea.odds_updated else "Brak kursów dla tego meczu w darmowym planie")
    if not ea.known:
        flags.append("Za mało danych historycznych o jednej z drużyn — brak rekomendacji")
    if ev["sport"] == "football":
        flags.append("Brak xG w darmowym źródle — model oparty na bramkach")
    if absences is None:
        flags.append("Brak danych o kontuzjach")
    inj_ts = conn.execute("SELECT MAX(fetched_at) AS t FROM injuries WHERE league_key = ?", (ev["league_key"],)).fetchone()["t"]
    sources = [
        {"kind": "fixtures", "provider": "API-SPORTS", "updatedAt": ev["updated_at"], "freshness": freshness(parse(ev["updated_at"]), now, 26)},
        {"kind": "odds", "provider": "The Odds API", "updatedAt": iso(ea.odds_updated) if ea.odds_updated else None, "freshness": freshness(ea.odds_updated, now, MAX_ODDS_AGE_H)},
        {"kind": "stats", "provider": "API-SPORTS", "updatedAt": ev["updated_at"], "freshness": freshness(parse(ev["updated_at"]), now, 26)},
        {"kind": "injuries", "provider": "API-Football", "updatedAt": inj_ts if absences is not None else None, "freshness": "fresh" if absences is not None else "missing"},
        {"kind": "lineups", "provider": "API-Football", "updatedAt": None, "freshness": "missing"},
    ]
    if ev["sport"] == "football":
        sources.append({"kind": "xg", "provider": "—", "updatedAt": None, "freshness": "missing"})
    active = [r for r in recs if r["status"] == "active"]
    return {
        "id": ev["id"],
        "origin": "live",
        "sport": ev["sport"],
        "league": {"id": lg.key, "name": lg.name, "country": lg.country, "sport": lg.sport},
        "home": team_json(ev["home_team_id"], ev["home_name"], ev["home_short"], ev["home_logo"]),
        "away": team_json(ev["away_team_id"], ev["away_name"], ev["away_short"], ev["away_logo"]),
        "kickoff": ev["kickoff"],
        "status": ev["status"],
        "venue": ev["venue"],
        "markets": [market_json(ev["sport"], m, ev["id"]) for m in ea.markets if any(s.quotes for s in m.selections)]
        + [{"market": t, "name": n, "margin": None, "selections": [], "available": False, "verdict": UNAVAILABLE_REASON} for t, n in UNAVAILABLE[ev["sport"]]],
        "recommendations": [rec_json(r, ev["sport"]) for r in recs],
        "noBetReason": None if active else NO_BET,
        "formHome": fh,
        "formAway": fa,
        "stats": stats_json(ev["sport"], fh, fa, ea),
        "absences": absences,
        "lineups": {"status": "unavailable", "home": [], "away": [], "updatedAt": None},
        "h2h": h2h_json(conn, ev),
        "sources": sources,
        "lastUpdated": max(filter(None, [ev["updated_at"], iso(ea.odds_updated) if ea.odds_updated else None])),
        "flags": flags,
    }


def history_json(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT r.*, e.sport, e.kickoff, e.league_key, e.home_score, e.away_score, h.name AS hn, w.name AS an
           FROM recommendations r JOIN events e ON e.id = r.event_id
           JOIN teams h ON h.id = e.home_team_id JOIN teams w ON w.id = e.away_team_id
           ORDER BY e.kickoff DESC""",
    ).fetchall()
    out = []
    for r in rows:
        result = "withdrawn" if r["status"] == "withdrawn" else (r["result"] or "pending")
        out.append(
            {
                "id": r["id"],
                "origin": "live",
                "sport": r["sport"],
                "eventLabel": f"{r['hn']} – {r['an']}",
                "league": LEAGUE_BY_KEY[r["league_key"]].name,
                "kickoff": r["kickoff"],
                "market": MARKET_TYPE[(r["sport"], r["market"])],
                "label": r["label"],
                "bookmaker": r["bookmaker"],
                "openingPrice": r["price"],
                "closingPrice": r["closing_price"],
                "clv": clv(r),
                "modelProb": r["model_prob"],
                "ev": r["ev"],
                "quality": r["quality"],
                "risk": r["risk"],
                "generatedAt": r["generated_at"],
                "result": result,
                "finalScore": f"{r['home_score']}:{r['away_score']}" if r["status"] == "settled" and r["home_score"] is not None else None,
                "profit": r["profit"] or 0.0,
            }
        )
    return out


def notifications_json(conn: sqlite3.Connection, now: datetime) -> list[dict[str, Any]]:
    since = iso(now - timedelta(hours=48))
    out: list[dict[str, Any]] = []
    for r in conn.execute(
        """SELECT r.*, h.short_name AS hs, w.short_name AS ws FROM recommendations r JOIN events e ON e.id = r.event_id
           JOIN teams h ON h.id = e.home_team_id JOIN teams w ON w.id = e.away_team_id WHERE r.updated_at >= ? OR r.generated_at >= ? OR r.settled_at >= ?""",
        (since, since, since),
    ):
        match = f"{r['hs']} – {r['ws']}"
        if r["generated_at"] >= since:
            out.append({"id": f"n-new-{r['id']}", "at": r["generated_at"], "kind": "new_value", "title": "Nowa okazja z dodatnim EV", "body": f"{match}: {r['label']} @ {r['price']:.2f} (EV +{pct(r['ev'])})", "eventId": r["event_id"], "read": False})
        if r["status"] == "withdrawn" and r["updated_at"] >= since:
            out.append({"id": f"n-wd-{r['id']}", "at": r["updated_at"], "kind": "withdrawn", "title": "Rekomendacja wycofana", "body": f"{match}: {r['withdraw_reason']}", "eventId": r["event_id"], "read": False})
        if r["settled_at"] and r["settled_at"] >= since:
            res = {"won": "trafiony", "lost": "nietrafiony", "void": "zwrot"}.get(r["result"], r["result"])
            out.append({"id": f"n-st-{r['id']}", "at": r["settled_at"], "kind": "settled", "title": "Rozliczono typ", "body": f"{match}: {r['label']} — {res}", "eventId": r["event_id"], "read": True})
    return sorted(out, key=lambda n: n["at"], reverse=True)[:30]


def provider_health(conn: sqlite3.Connection, configured: dict[str, bool]) -> list[dict[str, Any]]:
    meta = {
        "api-football": ("API-Football", "Terminarze, wyniki, kontuzje (piłka)"),
        "api-basketball": ("API-Basketball", "Terminarze i wyniki (NBA, Euroliga)"),
        "the-odds-api": ("The Odds API", "Kursy bukmacherów (1X2, gole, handicap)"),
    }
    out = []
    for pid, (name, purpose) in meta.items():
        last = conn.execute("SELECT * FROM provider_calls WHERE provider = ? AND http_status IS NOT NULL ORDER BY id DESC LIMIT 1", (pid,)).fetchone()
        status = "not_configured" if not configured.get(pid) else ("connected" if last and last["ok"] else "error" if last else "not_configured")
        quota = f"pozostało {last['remaining']}" if last and last["remaining"] is not None else None
        out.append({"id": pid, "name": name, "purpose": purpose, "status": status, "lastSync": last["called_at"] if last else None, "quota": quota})
    out.append({"id": "pl-books", "name": "STS · Fortuna · Superbet · Betclic", "purpose": "Kursy polskich bukmacherów", "status": "unverified", "lastSync": None, "quota": None})
    return out


def write_all(conn: sqlite3.Connection, analyses: list[EventAnalysis], now: datetime, out_dir: Path, configured: dict[str, bool], run_kind: str) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    events = [event_json(conn, a, now) for a in analyses]
    history = history_json(conn)
    meta = {
        "origin": "live",
        "generatedAt": iso(now),
        "runKind": run_kind,
        "bookmakers": bookmaker_titles(conn),
        "providers": provider_health(conn, configured),
        "notifications": notifications_json(conn, now),
        "backtestAvailable": False,
    }
    for name, payload in (("events.json", events), ("history.json", history), ("meta.json", meta)):
        tmp = out_dir / f".{name}.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(out_dir / name)
    return {"events": len(events), "history": len(history)}
