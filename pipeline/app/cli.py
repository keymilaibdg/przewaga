"""Entry point used by GitHub Actions.

  python -m app.cli run --kind morning     # full daily update
  python -m app.cli run --kind afternoon   # optional second pass, only if the odds budget allows
  python -m app.cli status                 # print budgets and last run

Environment (GitHub Secrets): FOOTBALL_DATA_KEY, BALLDONTLIE_KEY, ODDS_API_KEY.
Missing key => that provider is skipped. football-data.co.uk CSV files need no key.

Order of a morning run:
  football-data.org -> CSV history -> balldontlie -> The Odds API /events (free) -> /scores (only leagues
  with results to collect) -> /odds -> analysis -> publication. Results are fetched before odds so that a tight
  odds budget never blocks settling the tips.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from typing import Callable

from . import analysis, ingest, insight, params, publish, teams
from .config import (
    LEAGUE_BY_KEY,
    BDL_DAILY_LIMIT,
    CSV_DAILY_LIMIT,
    DB_PATH,
    FDO_DAILY_LIMIT,
    LEAGUES,
    ODDS_MARKETS,
    ODDS_MONTHLY_CREDITS,
    ODDS_REGIONS,
    PUBLISH_DIR,
    LeagueConfig,
    previous_season,
    season_for,
)
from .db import connect, dumps
from .providers import balldontlie, clubelo, fd_csv, football_data_org, nba_injuries
from .providers.balldontlie import Balldontlie
from .providers.fd_csv import FootballDataCsv
from .providers.football_data_org import FootballDataOrg
from .providers.http import ApiClient, BudgetExceeded, ProviderError, Transport, UrllibTransport, api_sports_budget, iso, odds_budget, utcnow
from .providers.odds_api import BASE as ODDS_BASE
from .providers.odds_api import OddsApi

log = logging.getLogger("przewaga")

# A result is expected this long after kickoff.
RESULT_AFTER = timedelta(hours=2, minutes=30)
# /scores?daysFrom=3 covers three days: one call every ~2 days per league is enough unless a tip waits for settlement.
SCORES_URGENT_AFTER = timedelta(hours=40)

ENV_KEYS = {"fdo": "FOOTBALL_DATA_KEY", "bdl": "BALLDONTLIE_KEY", "odds": "ODDS_API_KEY"}


class Pipeline:
    def __init__(
        self,
        conn: sqlite3.Connection,
        transport: Transport,
        keys: dict[str, str | None],
        clock: Callable[[], datetime] = utcnow,
        sleep: Callable[[float], None] | None = None,
        injury_parser: Callable[[bytes], list] | None = None,
    ) -> None:
        self.conn = conn
        self.clock = clock
        self.keys = keys
        self.transport = transport
        self.injury_parser = injury_parser or nba_injuries.parse_pdf
        self.errors: list[str] = []
        extra = {"sleep": sleep} if sleep else {}
        daily = lambda p, n: api_sports_budget(conn, p, n, 0, clock)  # noqa: E731 - daily request counter
        fk, bk, ok = keys.get("fdo"), keys.get("bdl"), keys.get("odds")
        self.fdo = FootballDataOrg(ApiClient("football-data-org", football_data_org.BASE, {"X-Auth-Token": fk or ""}, conn, transport, daily("football-data-org", FDO_DAILY_LIMIT), clock=clock, **extra)) if fk else None
        self.csv = FootballDataCsv(ApiClient("football-data-csv", fd_csv.BASE, {}, conn, transport, daily("football-data-csv", CSV_DAILY_LIMIT), clock=clock, **extra))
        self.bdl = Balldontlie(ApiClient("balldontlie", balldontlie.BASE, {"Authorization": bk or ""}, conn, transport, daily("balldontlie", BDL_DAILY_LIMIT), clock=clock, **extra)) if bk else None
        self.elo = ApiClient("clubelo", clubelo.BASE, {}, conn, transport, daily("clubelo", 4), clock=clock, **extra)
        self.odds = OddsApi(ApiClient("the-odds-api", ODDS_BASE, {"apiKey": ok or ""}, conn, transport, odds_budget(conn, ODDS_MONTHLY_CREDITS, clock), auth_in_query=True, clock=clock, **extra)) if ok else None

    # ---- helpers ----
    def _guard(self, label: str, fn: Callable[[], object]) -> object | None:
        try:
            return fn()
        except BudgetExceeded as e:
            self.errors.append(f"pominięto ({label}): {e}")
        except ProviderError as e:
            self.errors.append(f"błąd ({label}): {e}")
        except Exception as e:  # noqa: BLE001 - one failing league must not stop the run
            log.exception("unexpected error in %s", label)
            self.errors.append(f"błąd ({label}): {type(e).__name__}: {e}")
        return None

    def _count(self, sql: str, *args: object) -> int:
        return self.conn.execute(sql, args).fetchone()[0]

    def _events_between(self, lg: LeagueConfig, start: datetime, end: datetime) -> int:
        return self._count("SELECT COUNT(*) FROM events WHERE league_key = ? AND status = 'scheduled' AND kickoff BETWEEN ? AND ?", lg.key, iso(start), iso(end))

    # ---- steps ----
    def fetch_fdo(self, leagues: list[LeagueConfig]) -> int:
        if self.fdo is None:
            return 0
        now, n = self.clock(), 0
        for lg in (x for x in leagues if x.fixtures_source == "fdo" and x.fdo_code):
            fx = self._guard(f"terminarz {lg.key}", lambda lg=lg: self.fdo.matches(lg.key, lg.fdo_code, season_for(lg.sport, now)))
            if fx:
                n += ingest.store_fixtures(self.conn, fx, now, "fdo")  # type: ignore[arg-type]
        return n

    def fetch_history(self) -> int:
        """football-data.co.uk: current season daily (morning), previous season once."""
        now, n = self.clock(), 0
        for lg in (x for x in LEAGUES if x.csv_file):
            cur = season_for(lg.sport, now)
            prev = previous_season(lg.sport, cur)
            have_prev = self._count("SELECT COUNT(*) FROM events WHERE league_key = ? AND season = ? AND id LIKE 'fb:csv:%'", lg.key, prev)
            seasons = [cur] if have_prev and not lg.csv_file.startswith("new/") else [cur, prev]
            fx = self._guard(f"historia {lg.key}", lambda lg=lg, seasons=seasons: self.csv.results(lg.key, lg.csv_file, seasons))
            if fx:
                n += ingest.store_fixtures(self.conn, fx, now, "csv")  # type: ignore[arg-type]
        return n

    def fetch_bdl(self, incremental_only: bool = False) -> int:
        """NBA: full previous and current season once (~13 pages each), then only a date window."""
        if self.bdl is None:
            return 0
        now, n = self.clock(), 0
        for lg in (x for x in LEAGUES if x.fixtures_source == "bdl"):
            cur = season_for(lg.sport, now)
            jobs: list[tuple[str, object, object]] = []
            for s in (previous_season(lg.sport, cur), cur):
                if not incremental_only and self._count("SELECT COUNT(*) FROM events WHERE league_key = ? AND season = ?", lg.key, s) == 0:
                    jobs.append((s, None, None))
            if not any(s == cur for s, _, _ in jobs):
                jobs.append((cur, (now - timedelta(days=3)).date(), (now + timedelta(days=8)).date()))
            for s, start, end in jobs:
                fx = self._guard(f"mecze {lg.key} {s}", lambda s=s, start=start, end=end, lg=lg: self.bdl.games(lg.key, s, start, end))
                if fx:
                    n += ingest.store_fixtures(self.conn, fx, now, "bdl")  # type: ignore[arg-type]
        return n

    def fetch_odds_events(self) -> int:
        if self.odds is None:
            return 0
        now, n = self.clock(), 0
        for lg in (x for x in LEAGUES if x.fixtures_source == "odds"):
            evs = self._guard(f"terminarz {lg.key}", lambda lg=lg: self.odds.events(lg.odds_key))
            if evs is not None:
                n += ingest.store_odds_events(self.conn, lg, evs, now)  # type: ignore[arg-type]
        return n

    def fetch_scores(self) -> dict[str, int]:
        """Results for odds-sourced leagues. 2 credits per call, so only when something waits for a result."""
        if self.odds is None:
            return {}
        now, out = self.clock(), {}
        for lg in (x for x in LEAGUES if x.fixtures_source == "odds"):
            waiting = self.conn.execute(
                "SELECT id, kickoff FROM events WHERE league_key = ? AND status IN ('scheduled','live') AND kickoff BETWEEN ? AND ?",
                (lg.key, iso(now - timedelta(days=3)), iso(now - RESULT_AFTER)),
            ).fetchall()
            if not waiting:
                continue
            oldest = min(analysis.parse(r["kickoff"]) for r in waiting)
            tips = self._count(
                f"SELECT COUNT(*) FROM recommendations WHERE status = 'active' AND event_id IN ({','.join('?' * len(waiting))})", *[r["id"] for r in waiting]
            )
            if not tips and now - oldest < SCORES_URGENT_AFTER:
                continue  # tomorrow's call still covers these games
            sc = self._guard(f"wyniki {lg.key}", lambda lg=lg: self.odds.scores(lg.odds_key, 3))
            if sc is not None:
                out[lg.key] = ingest.store_scores(self.conn, lg, sc, now)  # type: ignore[arg-type]
        return out

    def fetch_odds(self, horizon_h: int) -> dict[str, int]:
        if self.odds is None:
            return {}
        now = self.clock()
        todo = [(lg, self._events_between(lg, now, now + timedelta(hours=horizon_h))) for lg in LEAGUES]
        todo = sorted([t for t in todo if t[1] > 0], key=lambda t: -t[1])
        out: dict[str, int] = {}
        for lg, _ in todo:
            evs = self._guard(f"kursy {lg.key}", lambda lg=lg: self.odds.odds(lg.odds_key, ODDS_MARKETS[lg.sport], ODDS_REGIONS))
            if evs is not None:
                res = ingest.store_odds(self.conn, lg, evs, now)  # type: ignore[arg-type]
                out[lg.key] = res["matched"]
                if res["unmatched"] and lg.fixtures_source != "odds":
                    self.errors.append(f"uwaga (kursy {lg.key}): {res['unmatched']} meczów z kursami bez pary w terminarzu")
        return out

    def fetch_nba_injuries(self) -> int:
        """Newest official NBA injury report -> injuries table (snapshot: replaces the previous one)."""
        raw = getattr(self.transport, "get_raw", None)
        now = self.clock()
        if raw is None or not self._events_between(LEAGUE_BY_KEY["nba"], now - timedelta(hours=3), now + timedelta(hours=36)):
            return 0
        tries = 0

        def get(url: str) -> tuple[int, bytes]:
            nonlocal tries
            tries += 1
            return raw(url)

        found = nba_injuries.latest(now, get)
        url = found[0] if found else nba_injuries.BASE
        self.conn.execute(
            "INSERT INTO provider_calls(provider, endpoint, http_status, ok, error, cost, called_at) VALUES (?,?,?,?,?,?,?)",
            ("nba-injury-report", url.rsplit("/", 1)[-1], 200 if found else 404, int(bool(found)), None if found else "brak raportu w ostatnich 12 h", tries, iso(now)),
        )
        self.conn.commit()
        if not found:
            self.errors.append("uwaga (raport kontuzji NBA): nie znaleziono raportu z ostatnich 12 godzin")
            return 0
        try:
            entries = self.injury_parser(found[1])
        except Exception as e:  # noqa: BLE001 - a changed PDF layout must not stop the run
            self.errors.append(f"uwaga (raport kontuzji NBA): nie udało się odczytać PDF: {type(e).__name__}: {e}")
            return 0
        return ingest.store_nba_injuries(self.conn, entries, now)

    def fetch_clubelo(self) -> int:
        now = self.clock()
        try:
            body = self.elo.get(now.strftime("%Y-%m-%d")).body
        except (ProviderError, BudgetExceeded) as e:
            self.errors.append(f"uwaga (ClubElo): {e}")
            return 0
        rows = clubelo.parse(body) if isinstance(body, str) else []
        if not rows:
            self.errors.append("uwaga (ClubElo): pusta odpowiedź")
            return 0
        self.conn.execute("DELETE FROM clubelo")
        self.conn.executemany(
            "INSERT OR REPLACE INTO clubelo(club, country, level, elo, rank, as_of) VALUES (?,?,?,?,?,?)",
            [(r.club, r.country, r.level, r.elo, r.rank, iso(now)) for r in rows],
        )
        self.conn.commit()
        return len(rows)

    def analyse_and_publish(self, run_kind: str) -> dict[str, object]:
        now = self.clock()
        settled = analysis.settle(self.conn, now)
        league_params = params.load()
        models = analysis.fit_models(self.conn, now, league_params)
        stats = {"new": 0, "updated": 0, "withdrawn": 0}
        analyses = []
        buckets = insight.load_buckets()
        for ev in analysis.upcoming_events(self.conn, now):
            a = analysis.analyse_event(self.conn, ev, models.get(ev["league_key"]), now, league_params.get(ev["league_key"]))
            try:
                a.insight = insight.build(self.conn, a, models.get(ev["league_key"]), buckets)
            except Exception as e:  # noqa: BLE001 - an insight must never block publishing
                log.exception("insight failed for %s", ev["id"])
                self.errors.append(f"uwaga (analiza kursu {ev['id']}): {type(e).__name__}: {e}")
            for k, v in analysis.sync_recommendations(self.conn, a, now).items():
                stats[k] += v
            analyses.append(a)
        configured = {"football-data-org": bool(self.fdo), "football-data-csv": True, "balldontlie": bool(self.bdl), "the-odds-api": bool(self.odds), "nba-injury-report": True, "clubelo": True}
        written = publish.write_all(self.conn, analyses, now, PUBLISH_DIR, configured, run_kind, league_params)
        return {"settled": settled, **stats, **written}

    def run(self, kind: str) -> dict[str, object]:
        started = self.clock()
        run_id = self.conn.execute("INSERT INTO runs(kind, started_at) VALUES (?, ?)", (kind, iso(started))).lastrowid
        self.conn.commit()
        merged = teams.merge_split_teams(self.conn)
        if kind == "morning":
            fixtures = {"football-data.org": self.fetch_fdo(list(LEAGUES)), "balldontlie": 0, "the-odds-api": 0}
            history = self.fetch_history()
            fixtures["balldontlie"] = self.fetch_bdl()
            fixtures["the-odds-api"] = self.fetch_odds_events()
            scores = self.fetch_scores()
            odds = self.fetch_odds(horizon_h=36)
            extra = {"clubelo": self.fetch_clubelo(), "nba_injuries": self.fetch_nba_injuries()}
        else:
            today = [lg for lg in LEAGUES if self._events_between(lg, started - timedelta(hours=14), started + timedelta(hours=12))]
            fixtures = {"football-data.org": self.fetch_fdo(today)}
            if any(lg.fixtures_source == "bdl" for lg in today):
                fixtures["balldontlie"] = self.fetch_bdl(incremental_only=True)
            history, scores = 0, {}
            odds = self.fetch_odds(horizon_h=10)
            extra = {"nba_injuries": self.fetch_nba_injuries()}
        result = self.analyse_and_publish(kind)
        summary = {"fixtures": fixtures, "csv_history": history, "teams_merged": merged, "scores": scores, "odds_matched": odds, **extra, **result, "errors": self.errors}
        critical = [e for e in self.errors if not e.startswith("uwaga")]
        self.conn.execute("UPDATE runs SET finished_at = ?, ok = ?, summary = ? WHERE id = ?", (iso(self.clock()), int(not critical), dumps(summary), run_id))
        self.conn.commit()
        return summary


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="przewaga")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--kind", choices=["morning", "afternoon"], default="morning")
    sub.add_parser("status")
    args = p.parse_args(argv)

    conn = connect(DB_PATH)
    keys = {k: os.environ.get(env) or None for k, env in ENV_KEYS.items()}
    pipe = Pipeline(conn, UrllibTransport(), keys)
    if args.cmd == "status":
        print(json.dumps({
            "odds_credits_today": odds_budget(conn, ODDS_MONTHLY_CREDITS)(),
            "football_data_org_left_today": api_sports_budget(conn, "football-data-org", FDO_DAILY_LIMIT, 0)(),
            "balldontlie_left_today": api_sports_budget(conn, "balldontlie", BDL_DAILY_LIMIT, 0)(),
            "last_run": dict(conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone() or {}),
            "now": iso(utcnow()),
        }, ensure_ascii=False, indent=2, default=str))
        return 0
    missing = [env for k, env in ENV_KEYS.items() if not keys[k]]
    if missing:
        log.warning("Brak kluczy API: %s — te źródła zostaną pominięte.", ", ".join(missing))
    summary = pipe.run(args.kind)
    conn.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0  # provider errors are reported in summary/meta, the run itself succeeded


if __name__ == "__main__":
    sys.exit(main())
