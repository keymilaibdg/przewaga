# ETAP 5: backtest walk-forward i kalibracja — stan projektu

Stan na 2026-11-18 (gałąź `etap-5`, repozytorium github.com/keymilaibdg/przewaga). Pełny raport z liczbami: [BACKTEST.md](BACKTEST.md).

## Co zbudowano
| Element | Plik | Opis |
|---|---|---|
| Dane historyczne | `pipeline/app/backtest/data.py` | football-data.co.uk z kursami (PL, La Liga, Bundesliga od 2019/20, Ekstraklasa — tylko kursy zamknięcia; Pinnacle → Betfair Exchange → średnia, gdy Pinnacle znika w 2025), archiwum kursów NBA sportsbookreviewsonline 2019/20–2022/23 (zamknięcie: moneyline, handicap, suma), puchary UEFA 2022–2024 z API-Football (18 zapytań jednorazowo, zapisane w `pipeline/backtest/data/`). Pamięć podręczna pobrań w `actions/cache`. |
| Walk-forward | `backtest/football.py`, `backtest/basketball.py` | Model dopasowywany tylko na meczach sprzed chwili prognozy (piłka co tydzień, NBA codziennie). Test sprawdza, że zmiana przyszłego wyniku nie zmienia wcześniejszych prognoz. |
| Ocena i dobór | `backtest/evaluate.py` | Log-loss, Brier, RPS, kalibracja, bootstrap; dobór XI, wagi model/rynek, skali niepewności, progów EV i rozbieżności na okresie strojenia; symulacja zakładów wywołuje ten sam `price_market`, co przebieg dzienny. |
| Parametry na żywo | `pipeline/app/params.py`, `pipeline/app/calibration.json` | Waga, skala, progi i status (`validated` / `validating` / `market_only`) per liga i rynek. Typy tylko dla `validated`. |
| Ratingi pucharowe | `pipeline/app/models/cups.py`, `pipeline/app/cup_ratings.json` | Łączny model: 21 lig krajowych (≈26,5 tys. meczów) + ≈2,6 tys. meczów pucharowych, 673 drużyny. Mapowanie nazw (aliasy, skróty CSV). LM: 36/36 drużyn rozpoznanych, LE: 33/36. |
| Workflow | `.github/workflows/backtest.yml` | Pełny backtest 1. dnia miesiąca (04:30 UTC), ratingi pucharowe w poniedziałki (05:40 UTC), ręcznie: Actions → „Backtest i kalibracja”. Wyniki zapisywane na gałąź. |
| Aplikacja (v0.4) | `frontend/src/pages/Stats.tsx`, `staticProvider.ts`, `MatchDetail.tsx` | Statystyki → Backtest: karta „Status modeli” + symulowane typy z okresu testowego (`backtest.json`). W meczu: „Model X% (sam model Y%)”. |
| Inne | `models/football.py`, `matching.py` | Gradient analityczny Dixon–Coles (ten sam wynik, ~100× szybciej), skróty nazw rozpoznawane w obu kierunkach („Eintracht Frankfurt” ↔ „Ein Frankfurt”). |

Testy: 44/44 (w tym backtest end-to-end na syntetycznych archiwach, test braku wycieku danych, parsowanie archiwum NBA, bramka typów z kalibracji, mapowanie drużyn pucharowych).

## Wynik (najważniejsze)
- **Na każdym rynku (PL, La Liga, Bundesliga, Ekstraklasa, NBA; 1X2, O/U, handicap) optymalna waga modelu = 0.** Każda domieszka modelu pogarsza log-loss względem rynku bez marży, monotonicznie (krzywe w `pipeline/backtest/results.json`). Model oparty tylko na wynikach (bez xG, składów, kontuzji) jest lepszy od naiwnych częstości, ale gorszy od rynku.
- Skutek: wszystkie ligi mają status „w walidacji”, typy są wyłączone. 14 aktywnych typów NBA zostanie wycofanych przy pierwszym przebiegu po scaleniu z powodem „Backtest walk-forward nie wykazał przewagi modelu nad rynkiem”. Wcześniejsze EV 2–6% wynikało z wagi 0,5 przyjętej bez weryfikacji.
- Puchary: ratingi lepsze od punktu odniesienia (log-loss 0,992 vs 1,032 na 461 meczach 2024/25), ale bez historii kursów pucharowych nie da się sprawdzić przewagi nad rynkiem → waga jak w ligach krajowych (0), status „w walidacji”.
- Obserwacja do decyzji: przy wadze 0 symulacja wciąż znajduje nieliczne zakłady, gdzie najlepszy kurs rynku przewyższa kurs godziwy Pinnacle/Betfair (łącznie ok. 90 zakładów w 7 sezonach 4 lig, EV wobec linii zamknięcia od +3% do +17%, próba zbyt mała na wnioski). To przewaga z porównywania kursów, nie z modelu, a dotyczy kursów zagranicznych bukmacherów.

## Do zrobienia / decyzje użytkownika
1. Scalić `etap-5` → `main` (PR: github.com/keymilaibdg/przewaga/compare/main...etap-5). Po scaleniu: APK v0.4.x zbuduje się sam; harmonogram backtestu działa tylko na `main`.
2. Decyzja: czy dodać „tryb rynkowy” (typ = kurs bukmachera powyżej kursu godziwego rynku ostrego, bez modelu) z wyraźnym oznaczeniem — wymaga kursów polskich bukmacherów, których darmowe źródła nie mają.
3. ETAP 6 (kupony, powiadomienia) bez zmian w planie.
