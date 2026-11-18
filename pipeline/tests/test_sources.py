"""ETAP 4 data sources: team identity across sources, football-data.org, CSV history, balldontlie, odds-only events."""
from datetime import datetime, timedelta, timezone

import pytest

from app import ingest, teams
from app.db import connect
from app.providers.common import Fixture, TeamRef
from app.providers.football_data_org import FootballDataOrg
from app.providers.http import ApiClient, HttpResponse

NOW = datetime(2026, 11, 17, 7, 0, tzinfo=timezone.utc)


class Canned:
    """Transport returning fixed bodies by URL substring; records requested URLs and headers."""

    def __init__(self, routes: dict[str, object], headers: dict[str, str] | None = None) -> None:
        self.routes = routes
        self.headers = headers or {}
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, headers: dict[str, str]) -> HttpResponse:
        self.calls.append((url, headers))
        for k, body in self.routes.items():
            if k in url:
                return HttpResponse(200, dict(self.headers), body)
        return HttpResponse(404, {}, {"message": "not found"})


def client(conn, transport, provider="football-data-org", auth=None):
    return ApiClient(provider, "https://example.test/v4", auth or {"X-Auth-Token": "k"}, conn, transport, lambda: 100, sleep=lambda s: None, clock=lambda: NOW)


@pytest.fixture()
def conn(tmp_path):
    return connect(tmp_path / "db.sqlite3")


def fx(id_, home, away, ko, status="finished", hs=1, as_=0, league="epl", sport="football", season="2026", hid=None, aid=None):
    return Fixture(id_, sport, league, season, TeamRef(hid, home), TeamRef(aid, away), ko, status, hs if status == "finished" else None, as_ if status == "finished" else None, None)


# ---------- team identity ----------

def test_resolver_maps_csv_names_onto_football_data_org_teams(conn):
    for native, name in (("fdo:66", "Manchester United FC"), ("fdo:65", "Manchester City FC"), ("fdo:351", "Nottingham Forest FC"), ("fdo:19", "Eintracht Frankfurt")):
        teams.resolve(conn, "epl", "fdo", TeamRef(native, name, short="XXX"))
    assert teams.resolve(conn, "epl", "csv", TeamRef(None, "Man United")) == "fdo:66"
    assert teams.resolve(conn, "epl", "csv", TeamRef(None, "Man City")) == "fdo:65"
    assert teams.resolve(conn, "epl", "csv", TeamRef(None, "Nott'm Forest")) == "fdo:351"
    assert teams.resolve(conn, "epl", "csv", TeamRef(None, "Ein Frankfurt")) == "fdo:19"
    # unknown name -> new team, never a wrong merge
    assert teams.resolve(conn, "epl", "csv", TeamRef(None, "Sunderland")) == "csv:epl:sunderland"
    # display name without the 'FC' suffix
    assert conn.execute("SELECT name FROM teams WHERE id = 'fdo:66'").fetchone()["name"] == "Manchester United"


def test_resolver_never_merges_two_names_from_one_source(conn):
    lechia = teams.resolve(conn, "ekstraklasa", "csv", TeamRef(None, "Lechia"))
    lech = teams.resolve(conn, "ekstraklasa", "csv", TeamRef(None, "Lech"))
    assert lech != lechia
    assert teams.resolve(conn, "ekstraklasa", "odds", TeamRef(None, "Lech Poznań")) == lech
    assert teams.resolve(conn, "ekstraklasa", "odds", TeamRef(None, "Lechia Gdańsk")) == lechia
    assert teams.resolve(conn, "ekstraklasa", "odds", TeamRef(None, "Górnik Zabrze"), create=False) is None
    # 'ł' is not decomposed by NFKD: without transliteration 'Wrocław' became 'wrocaw' and never matched
    slask = teams.resolve(conn, "ekstraklasa", "csv", TeamRef(None, "Slask Wroclaw"))
    assert teams.resolve(conn, "ekstraklasa", "odds", TeamRef(None, "Śląsk Wrocław")) == slask
    assert teams.slug("Widzew Łódź") == "widzew-lodz"
    assert conn.execute("SELECT name FROM teams WHERE id = ?", (slask,)).fetchone()["name"] == "Śląsk Wrocław", "fuller name replaces the CSV one"


def test_same_match_from_two_sources_is_stored_once(conn):
    ko = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
    # CSV first (date only, no exact time), then football-data.org with the exact kickoff and a delayed result
    ingest.store_fixtures(conn, [fx("fb:csv:epl:2026-11-08:liverpool:arsenal", "Liverpool", "Arsenal", ko.replace(hour=0), hs=2, as_=1)], NOW, "csv")
    ingest.store_fixtures(conn, [fx("fb:fdo:1", "Liverpool FC", "Arsenal FC", ko, status="scheduled", hid="fdo:64", aid="fdo:57")], NOW, "fdo")
    rows = conn.execute("SELECT * FROM events").fetchall()
    assert len(rows) == 1
    r = rows[0]
    assert r["kickoff"] == "2026-11-08T15:00:00Z", "exact time from football-data.org wins"
    assert (r["status"], r["home_score"], r["away_score"]) == ("finished", 2, 1), "a known result is never downgraded"


# ---------- football-data.org ----------

FDO_BODY = {
    "matches": [
        {"id": 1, "utcDate": "2026-11-08T15:00:00Z", "status": "FINISHED", "venue": "Anfield",
         "homeTeam": {"id": 64, "name": "Liverpool FC", "shortName": "Liverpool", "tla": "LIV", "crest": "https://crests.football-data.org/64.png"},
         "awayTeam": {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal", "tla": "ARS", "crest": None},
         "score": {"duration": "REGULAR", "fullTime": {"home": 2, "away": 1}}},
        {"id": 2, "utcDate": "2026-11-22T17:30:00Z", "status": "TIMED",
         "homeTeam": {"id": 57, "name": "Arsenal FC", "tla": "ARS"}, "awayTeam": {"id": 64, "name": "Liverpool FC", "tla": "LIV"},
         "score": {"fullTime": {"home": None, "away": None}}},
        {"id": 3, "utcDate": "2026-11-23T17:30:00Z", "status": "POSTPONED",
         "homeTeam": {"id": 61, "name": "Chelsea FC"}, "awayTeam": {"id": 73, "name": "Tottenham Hotspur FC"}, "score": {}},
        {"id": 4, "utcDate": "2027-03-10T20:00:00Z", "status": "SCHEDULED", "homeTeam": {"id": None, "name": None}, "awayTeam": {"id": None, "name": None}, "score": {}},
        {"id": 5, "utcDate": "2026-11-05T20:00:00Z", "status": "FINISHED",
         "homeTeam": {"id": 86, "name": "Real Madrid CF"}, "awayTeam": {"id": 5, "name": "FC Bayern München"},
         "score": {"duration": "EXTRA_TIME", "regularTime": {"home": 1, "away": 1}, "fullTime": {"home": 2, "away": 1}}},
    ]
}


def test_football_data_org_parsing(conn):
    t = Canned({"competitions/PL/matches": FDO_BODY})
    out = FootballDataOrg(client(conn, t)).matches("epl", "PL", "2026")
    assert [f.id for f in out] == ["fb:fdo:1", "fb:fdo:2", "fb:fdo:3", "fb:fdo:5"], "slots without teams are skipped"
    assert t.calls[0][1]["X-Auth-Token"] == "k"
    f1, f2, f3, f5 = out
    assert (f1.status, f1.home_score, f1.away_score, f1.home.id, f1.home.short, f1.venue) == ("finished", 2, 1, "fdo:64", "LIV", "Anfield")
    assert (f2.status, f2.home_score) == ("scheduled", None)
    assert f3.status == "postponed"
    assert (f5.home_score, f5.away_score) == (1, 1), "bets settle on regular time, not after extra time"
    # the key never lands in the call log
    assert "k" not in conn.execute("SELECT params FROM provider_calls").fetchone()["params"]


# ---------- football-data.co.uk CSV ----------

E0_2526 = """﻿Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,PSCH,PSCD,PSCA
E0,15/08/2025,20:00,Liverpool,Bournemouth,4,2,H,1.30,6.0,9.5
E0,16/08/2025,12:30,Aston Villa,Newcastle,0,0,D,2.4,3.4,3.0
E0,17/05/26,15:00,Man United,Nott'm Forest,2,1,H,1.8,3.8,4.6
,,,,,,,,,,
"""
E0_2627 = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR\nE0,08/11/2026,15:00,Liverpool,Arsenal,2,1,H\nE0,09/11/2026,16:30,Chelsea,Spurs,,,\n"
POL = """Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PSCH,PSCD,PSCA
Poland,Ekstraklasa,2024/2025,20/05/2025,18:00,Legia,Lech,1,1,D,2.5,3.3,2.9
Poland,Ekstraklasa,2025/2026,19/07/2025,20:15,Lech,Lechia,3,0,H,1.5,4.2,6.0
Poland,Ekstraklasa,2026/2027,18/07/2026,17:30,Gornik Z.,Rakow,0,2,A,3.1,3.3,2.3
"""


def test_csv_history_parsing_and_season_filter(conn):
    from app.providers.fd_csv import FootballDataCsv, season_code

    assert season_code("2025") == "2526" and season_code("2099") == "9900"
    t = Canned({"mmz4281/2526/E0.csv": E0_2526, "mmz4281/2627/E0.csv": E0_2627, "new/POL.csv": POL})
    api = FootballDataCsv(client(conn, t, provider="football-data-csv", auth={}))
    epl = api.results("epl", "E0", ["2026", "2025"])
    assert len(epl) == 4, "blank lines and unplayed matches are skipped"
    first = next(f for f in epl if f.home.name == "Liverpool" and f.season == "2025")
    assert first.kickoff == datetime(2025, 8, 15, 19, 0, tzinfo=timezone.utc), "UK local time -> UTC"
    assert first.id == "fb:csv:epl:2025-08-15:liverpool:bournemouth" and first.home_score == 4
    assert any(f.home.name == "Man United" and f.kickoff.year == 2026 for f in epl), "two-digit years"
    pol = api.results("ekstraklasa", "new/POL", ["2026", "2025"])
    assert [f.home.name for f in pol] == ["Lech", "Gornik Z."], "older seasons ignored"


def test_csv_history_merges_into_football_data_org_teams(conn):
    from app.providers.fd_csv import parse

    fdo = FootballDataOrg(client(conn, Canned({"competitions/PL/matches": FDO_BODY}))).matches("epl", "PL", "2026")
    ingest.store_fixtures(conn, fdo[:2], NOW, "fdo")
    ingest.store_fixtures(conn, parse(E0_2627, "epl", {"2026"}), NOW, "csv")
    n = conn.execute("SELECT COUNT(*) n FROM events WHERE league_key = 'epl'").fetchone()["n"]
    assert n == 2, "the CSV row of a match already known from football-data.org is merged, not duplicated"
    ids = {r["id"] for r in conn.execute("SELECT id FROM teams")}
    assert ids == {"fdo:64", "fdo:57"}


def test_body_decoding_json_csv_and_latin1():
    from app.providers.http import decode_body

    assert decode_body(b'{"a": 1}', "application/json") == {"a": 1}
    assert decode_body(b"[]", "text/plain") == []
    assert decode_body("﻿Div,Date\n".encode("utf-8"), "text/csv") == "Div,Date\n"
    assert decode_body("Home\nGórnik".encode("latin-1"), "application/octet-stream") == "Home\nGórnik"


# ---------- balldontlie ----------

def _bdl_game(gid, home, away, status, hs=0, vs=0, dt="2025-10-22T00:00:00.000Z", day="2025-10-21"):
    team = lambda i, n, a: {"id": i, "full_name": n, "abbreviation": a, "name": n.split()[-1]}  # noqa: E731
    return {"id": gid, "date": day, "datetime": dt, "season": 2025, "status": status, "postseason": False,
            "home_team_score": hs, "visitor_team_score": vs, "home_team": team(*home), "visitor_team": team(*away)}


BOS, LAL, DEN = (2, "Boston Celtics", "BOS"), (14, "Los Angeles Lakers", "LAL"), (8, "Denver Nuggets", "DEN")


class Paged(Canned):
    def get(self, url, headers):
        self.calls.append((url, headers))
        if "cursor=" not in url:
            return HttpResponse(200, {}, {"data": [_bdl_game(1, BOS, LAL, "Final", 112, 104), _bdl_game(2, LAL, DEN, "Final", 99, 101)], "meta": {"next_cursor": 77, "per_page": 100}})
        return HttpResponse(200, {}, {"data": [
            _bdl_game(3, DEN, BOS, "3rd Qtr", 70, 68),
            _bdl_game(4, BOS, DEN, "2025-10-24T23:30:00Z", dt=None),
            _bdl_game(5, LAL, BOS, "7:30 pm ET", dt=None, day="2025-10-25"),
        ], "meta": {"per_page": 100}})


def test_balldontlie_paging_rate_limit_and_statuses(conn):
    from app.providers.balldontlie import Balldontlie

    slept: list[float] = []
    t = Paged({})
    c = ApiClient("balldontlie", "https://example.test/v1", {"Authorization": "bdl-key"}, conn, t, lambda: 100, sleep=slept.append, clock=lambda: NOW)
    games = Balldontlie(c).games("nba", "2025-2026")
    assert len(t.calls) == 2 and "cursor=77" in t.calls[1][0] and "seasons%5B%5D=2025" in t.calls[0][0]
    assert t.calls[0][1]["Authorization"] == "bdl-key"
    assert slept == [13], "5 requests/min: pause between pages"
    by = {g.id: g for g in games}
    assert (by["bb:bdl:1"].status, by["bb:bdl:1"].home_score, by["bb:bdl:1"].away_score) == ("finished", 112, 104)
    assert (by["bb:bdl:3"].status, by["bb:bdl:3"].home_score) == ("live", None)
    assert by["bb:bdl:4"].status == "scheduled" and by["bb:bdl:4"].kickoff == datetime(2025, 10, 24, 23, 30, tzinfo=timezone.utc)
    assert by["bb:bdl:5"].status == "scheduled" and by["bb:bdl:5"].kickoff == datetime(2025, 10, 25, 23, 30, tzinfo=timezone.utc)
    assert by["bb:bdl:1"].home.id == "bdl:2" and by["bb:bdl:1"].home.short == "BOS"


def test_per_minute_counters_are_not_a_daily_budget(conn):
    from app.providers.http import api_sports_budget

    t = Canned({"games": {"data": [], "meta": {}}}, headers={"x-ratelimit-remaining": "4", "x-ratelimit-requests-remaining": "4"})
    c = ApiClient("balldontlie", "https://example.test/v1", {}, conn, t, api_sports_budget(conn, "balldontlie", 60, 0, lambda: NOW), sleep=lambda s: None, clock=lambda: NOW)
    c.get("games")
    assert c.budget() == 59


# ---------- The Odds API as a fixtures/results source ----------

def _odds_event(eid, home, away, ko, price_home=2.1):
    return {"id": eid, "sport_key": "soccer_poland_ekstraklasa", "commence_time": ko, "home_team": home, "away_team": away,
            "bookmakers": [{"key": "pinnacle", "title": "Pinnacle", "last_update": "2026-11-17T06:00:00Z", "markets": [
                {"key": "h2h", "outcomes": [{"name": home, "price": price_home}, {"name": "Draw", "price": 3.4}, {"name": away, "price": 3.6}]}]}]}


def test_odds_league_events_odds_and_scores(conn):
    from app.config import LEAGUE_BY_KEY
    from app.providers.fd_csv import parse
    from app.providers.odds_api import OddsApi

    lg = LEAGUE_BY_KEY["ekstraklasa"]
    # history from the CSV first (names 'Lech', 'Gornik Z.')
    ingest.store_fixtures(conn, parse(POL, "ekstraklasa", {"2025", "2026"}), NOW, "csv")
    routes = {
        "/events": [{"id": "e1", "sport_key": lg.odds_key, "commence_time": "2026-11-21T17:30:00Z", "home_team": "Lech Poznań", "away_team": "Górnik Zabrze"}],
        "/odds": [_odds_event("e1", "Lech Poznań", "Górnik Zabrze", "2026-11-21T17:30:00Z")],
        "/scores": [
            {"id": "e1", "sport_key": lg.odds_key, "commence_time": "2026-11-21T17:30:00Z", "completed": True, "home_team": "Lech Poznań", "away_team": "Górnik Zabrze",
             "scores": [{"name": "Lech Poznań", "score": "2"}, {"name": "Górnik Zabrze", "score": "2"}]},
            {"id": "e0", "sport_key": lg.odds_key, "commence_time": "2026-11-15T15:00:00Z", "completed": True, "home_team": "Raków Częstochowa", "away_team": "Lech Poznań",
             "scores": [{"name": "Raków Częstochowa", "score": "1"}, {"name": "Lech Poznań", "score": "0"}]},
            {"id": "e9", "sport_key": lg.odds_key, "commence_time": "2026-11-23T15:00:00Z", "completed": False, "home_team": "A", "away_team": "B", "scores": None},
        ],
    }
    t = Canned(routes, headers={"x-requests-last": "0"})
    api = OddsApi(client(conn, t, provider="the-odds-api", auth={"apiKey": "o"}))
    assert ingest.store_odds_events(conn, lg, api.events(lg.odds_key), NOW) == 1
    ev = conn.execute("SELECT * FROM events WHERE id = 'odds:e1'").fetchone()
    assert ev and ev["status"] == "scheduled" and ev["season"] == "2026"
    lech = teams.resolve(conn, "ekstraklasa", "csv", TeamRef(None, "Lech"))
    assert ev["home_team_id"] == lech, "odds names land on the CSV history teams -> the model knows them"

    res = ingest.store_odds(conn, lg, api.odds(lg.odds_key, "h2h", "eu"), NOW)
    assert res["matched"] == 1 and res["created"] == 0 and res["quotes"] == 3

    assert ingest.store_scores(conn, lg, api.scores(lg.odds_key), NOW) == 2
    ev = conn.execute("SELECT * FROM events WHERE id = 'odds:e1'").fetchone()
    assert (ev["status"], ev["home_score"], ev["away_score"]) == ("finished", 2, 2)
    # a finished game never seen in /odds becomes history (teams resolved onto the CSV names)
    assert conn.execute("SELECT status FROM events WHERE id = 'odds:e0'").fetchone()["status"] == "finished"
    assert "daysFrom=3" in next(u for u, _ in t.calls if "/scores" in u)
    assert "apiKey" not in conn.execute("SELECT params FROM provider_calls WHERE endpoint LIKE '%scores'").fetchone()["params"]


def test_unmatched_odds_never_create_events_in_fixture_api_leagues(conn):
    from app.config import LEAGUE_BY_KEY
    from app.providers.odds_api import OddsEvent

    lg = LEAGUE_BY_KEY["epl"]
    oe = OddsEvent("x", lg.odds_key, NOW + timedelta(days=1), "Arsenal", "Chelsea", [])
    assert ingest.store_odds(conn, lg, [oe], NOW) == {"matched": 0, "unmatched": 1, "quotes": 0, "created": 0}
    assert conn.execute("SELECT COUNT(*) n FROM events").fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) n FROM teams").fetchone()["n"] == 0


def test_teams_split_by_old_matching_are_merged(conn):
    """Before the 'ł' fix 'Wisła Płock' (odds) did not match 'Wisla Plock' (CSV) and got its own team."""
    ko = NOW + timedelta(days=2)
    csv_team = teams.resolve(conn, "ekstraklasa", "csv", TeamRef(None, "Wisla Plock"))
    other = teams.resolve(conn, "ekstraklasa", "csv", TeamRef(None, "Legia"))
    conn.execute("INSERT INTO teams(id, name, short_name) VALUES ('odds:ekstraklasa:wisa-pock', 'Wisła Płock', 'WIS')")
    conn.execute("INSERT INTO team_aliases VALUES ('ekstraklasa', 'odds', 'Wisła Płock', 'odds:ekstraklasa:wisa-pock')")
    ingest.upsert(conn, "events", {"id": "odds:x", "sport": "football", "league_key": "ekstraklasa", "season": "2026", "home_team_id": "odds:ekstraklasa:wisa-pock",
                                   "away_team_id": other, "kickoff": ingest.iso(ko), "status": "scheduled", "home_score": None, "away_score": None, "venue": None, "updated_at": ingest.iso(NOW)})
    assert teams.merge_split_teams(conn) == 1
    assert conn.execute("SELECT home_team_id FROM events WHERE id = 'odds:x'").fetchone()["home_team_id"] == csv_team
    assert conn.execute("SELECT name FROM teams WHERE id = ?", (csv_team,)).fetchone()["name"] == "Wisła Płock"
    assert conn.execute("SELECT 1 FROM teams WHERE id = 'odds:ekstraklasa:wisa-pock'").fetchone() is None
    assert teams.merge_split_teams(conn) == 0, "idempotent"
