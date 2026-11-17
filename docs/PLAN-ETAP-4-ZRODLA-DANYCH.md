# ETAP 4: zmiana źródeł danych (plan dla następnej sesji)

Stan na 2026-11-17 18:45.

## Gdzie jest projekt
- Repozytorium: **github.com/keymilaibdg/przewaga** (publiczne, gałąź `main`; analizy publikowane w gałęzi `data`).
- APK: **v0.3.5** podpisany stałym kluczem, w Releases (`releases/latest`). Build działa (ubuntu-24.04, Capacitor 7, JDK 21).
- Klucz podpisu: zaszyfrowany PKCS#12 w `frontend/signing/przewaga-release.p12` (zgoda właściciela). Sekret: `ANDROID_KEYSTORE_PASSWORD`.
- Sekrety w repozytorium: `APISPORTS_KEY`, `ODDS_API_KEY`, `ANDROID_KEYSTORE_PASSWORD`, `FOOTBALL_DATA_KEY`, `BALLDONTLIE_KEY` (`ANDROID_KEYSTORE_B64` jest zbędny).
- Nowa sesja: sklonuj repozytorium (add_repo keymilaibdg/przewaga z dostępem push), testy: `cd pipeline && python -m pytest`.

## Problem wykryty przy pierwszym prawdziwym uruchomieniu
API-Football (plan Free) zwraca dla sezonów 2025 i 2026 błąd: `{"plan": "Free plans do not have access to this season, try from 2022 to 2024."}`. API-Basketball też zwraca błąd. Wynik: 0 wydarzeń w `events.json`.

## Nowe źródła (0 zł), uzgodnione z użytkownikiem
| Rola | Źródło | Uwagi |
|---|---|---|
| Terminarze + kursy, wszystkie 8 lig | The Odds API (`/v4/sports/{key}/odds`, region eu) | Klucze lig zweryfikowane: soccer_epl, soccer_spain_la_liga, soccer_germany_bundesliga, soccer_uefa_champs_league, soccer_uefa_europa_league, soccer_poland_ekstraklasa, basketball_nba, basketball_euroleague. 500 kredytów/mies. |
| Wyniki i terminarze: PL, La Liga, Bundesliga, Liga Mistrzów | football-data.org v4 (`X-Auth-Token`) | Free: 12 rozgrywek, 10 zapytań/min, tylko bieżący sezon, wyniki z opóźnieniem. Kody: PL, PD, BL1, CL. Brak Ligi Europy i Ekstraklasy. |
| Historia do nauki modelu (piłka) | football-data.co.uk CSV (bez klucza) | E0 (PL), SP1 (La Liga), D1 (Bundesliga): `mmz4281/{2526,2627}/{kod}.csv`. Ekstraklasa: sprawdzić plik `new/POL.csv`. Zawiera też kursy zamknięcia (Pinnacle), co przyda się do backtestu w ETAPIE 5. |
| NBA: mecze i wyniki | balldontlie (`Authorization: <key>`) | Free: drużyny, zawodnicy, mecze; 5 zapytań/min. Historię poprzedniego sezonu pobrać raz (paginacja), potem przyrostowo. |
| Wyniki LE, Ekstraklasy, Euroligi | The Odds API `/scores?daysFrom=3` | Kosztuje kredyty, więc tylko dla lig z typami do rozliczenia. |

## Projekt zmian w pipeline
1. `providers/football_data_org.py`: matches per competition (season bieżący), mapowanie statusów (SCHEDULED/TIMED → scheduled, FINISHED → finished, POSTPONED itd.), wynik `score.fullTime`.
2. `providers/fd_csv.py`: pobranie CSV (urllib), kolumny Date/Time/HomeTeam/AwayTeam/FTHG/FTAG, format daty dd/mm/yyyy, zapis jako zakończone mecze (id `fb:csv:<liga>:<data>:<home>:<away>`). Deduplikacja z football-data.org przez `matching.best_match` (okno czasu ±36 h, bo CSV bywa bez godziny).
3. `providers/balldontlie.py`: `/v1/games?seasons[]=…&per_page=100&cursor=…`; limit 5/min → `sleep(13)` między stronami; budżet w `provider_calls`.
4. Wydarzenia z kursów dla lig bez źródła terminarza (LE, Ekstraklasa, Euroliga): `ingest.store_odds` musi umieć **utworzyć** wydarzenie (id `odds:<event_id>`), gdy brak dopasowania. Wyniki później przez `/scores`.
5. Model: Liga Mistrzów i Liga Europy oraz Euroliga mają za mało historii → `both_teams_known = False` → bez rekomendacji (flaga w UI). Do rozważenia w ETAPIE 5: ratingi drużyn z lig krajowych dla pucharów.
6. `config.py`: per liga źródło terminarza (`fixtures_source`) i historii (`history_source`); usunąć zależność od API-SPORTS (zostawić adapter do backtestów 2022–2024).
7. `cli.py`: kolejność: football-data.org → CSV (raz dziennie) → balldontlie → kursy → wyniki z /scores (tylko potrzebne ligi) → analiza → publikacja.
8. Testy: rozszerzyć `tests/fake_api.py` o football-data.org, CSV, balldontlie i /scores. Zachować testy end-to-end i budżetów.
9. `update.yml`: dodać env `FOOTBALL_DATA_KEY`, `BALLDONTLIE_KEY`.
10. Profil → Źródła danych w aplikacji: nowe pozycje dostawców.

## Kryteria ukończenia
- Po ręcznym uruchomieniu „Aktualizacja danych” (morning) `events.json` zawiera mecze z 8 lig z kursami.
- Typy pojawiają się tylko tam, gdzie model ma historię i są spełnione progi.
- Brak błędów krytycznych w podsumowaniu przebiegu (adnotacje „Pipeline”).
- Aplikacja v0.3.x na telefonie pokazuje prawdziwe mecze.

## Postęp (gałąź `etap-4`)
| Krok | Stan | Co zrobiono |
|---|---|---|
| 1. football-data.org + tożsamość drużyn | ✅ | `providers/football_data_org.py` (statusy, wynik z czasu regulaminowego), `teams.py` (tabela `team_aliases`: nazwa ze źródła → jedno id drużyny), `ingest.store_fixtures(..., source)` scala ten sam mecz z dwóch źródeł (te same drużyny ±36 h, wynik nigdy nie jest cofany). Dopasowanie nazw rozumie skróty z CSV („Man United”, „Ein Frankfurt”, „Nott'm Forest”). |
