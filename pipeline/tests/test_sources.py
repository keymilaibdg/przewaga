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
