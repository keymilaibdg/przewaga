# Raport: ETAP 3 + przejście na APK (2026-11-17)

## Decyzje użytkownika w tej sesji
1. **0 zł.** Brak płatnego hostingu i serwera. GitHub Actions zastępuje backend i harmonogram.
2. **Ligi:** Premier League, La Liga, Bundesliga, Liga Mistrzów, Liga Europy, Ekstraklasa, NBA, Euroliga.
3. **Aktualizacje:** 1×/dzień rano, 2× tylko gdy pozwala limit kursów (decyduje automatycznie budżet).
4. **Aplikacja .APK** zamiast samej PWA. Dane w **publicznym** repozytorium GitHub.

## Uproszczenia względem briefu (świadome, uzgodnione)
- Zamiast PostgreSQL, Redis, Celery i FastAPI: SQLite + JSON + GitHub Actions.
- Brak logowania: aplikacja jednego użytkownika, ustawienia na telefonie.
- Aktualizacje 1–2×/dzień zamiast co kilka minut (limity darmowych API).
- Rynki: 1X2/moneyline, gole/punkty over-under, handicap (koszykówka). Podwójna szansa, BTTS, AH, rożne i kartki są niedostępne w darmowym planie kursów; aplikacja pokazuje to wprost.
- Brak xG i składów; kontuzje (piłka) pobierane, ale model v0 nie przelicza ich wpływu (zaznaczane w „argumentach przeciw”).

## Co zbudowano
**pipeline/** (Python, stdlib + NumPy/SciPy):
- `providers/`: API-Football, API-Basketball, The Odds API; klient HTTP z ponawianiem, logowaniem wywołań (bez kluczy) i budżetem (dzienny dla API-SPORTS, miesięczny rozłożony na dni dla kursów).
- `matching.py`: dopasowanie meczów między źródłami (czas ±6 h + nazwy, aliasy, ochrona przed derby i rewanżami).
- `models/football.py`: Dixon–Coles z zanikiem czasowym. `models/basketball.py`: ratingi (ridge) + rozkład normalny.
- `engine/evaluate.py`: kursy bez marży, korekta rynkowa (50/50), EV, ocena jakości, ryzyko. Twarde reguły: EV ≥ 2%, ocena ≥ 60, kurs ≤ 5, tylko linie połówkowe, świeże kursy, znane drużyny, rozbieżność model–rynek ≤ 12 p.p.
- `analysis.py`: cykl życia typów (nowy → wycofany z powodem / rozliczony), rozliczanie, CLV.
- `publish.py`: JSON zgodny z `frontend/src/types/domain.ts`.
- `.github/workflows/update.yml`: harmonogram, zapis bazy, publikacja gałęzi `data`.

**frontend/**:
- `StaticDataProvider`: dane live z JSON, kopia offline na urządzeniu, ekran „Brak danych” w APK (bez cichego DEMO).
- Minimalny kurs u polskiego bukmachera z 12% podatkiem od stawki (ustawienie 12% / 0%).
- Capacitor (`capacitor.config.json`, `assets/` z ikonami), sprawdzanie aktualizacji APK w Profilu.
- `.github/workflows/android.yml`: build APK, podpis stałym kluczem, publikacja w Releases.

## Testy
| Zestaw | Wynik |
|---|---|
| pytest (pipeline: matematyka, modele, silnik, dopasowanie, HTTP, budżety, end-to-end, cykl życia, rozliczanie) | 23 ZALICZONE |
| Jednostkowe TS (matematyka kursów + podatek) | 12 ZALICZONYCH |
| E2E tryb DEMO | 15 ZALICZONYCH |
| E2E tryb live (dane z pipeline) | 7 ZALICZONYCH |
| E2E tryb APK (brak danych, offline, wersja) | 5 ZALICZONYCH |
| Układ 360/390/412 px | 36 ZALICZONYCH |

**Naprawione błędy wykryte testami:** pomylenie „Manchester United” z „Manchester City” w dopasowaniu nazw; brak ochrony przed skrajną rozbieżnością model–rynek; niedeterministyczne dane testowe; odwrócone prawdopodobieństwo w danych testowych NBA.

**NIEWYKONANE** (wymaga Twoich kluczy lub serwerów GitHub):
- prawdziwe odpowiedzi API (zakres darmowego planu, pokrycie Ekstraklasy i Euroligi kursami);
- build APK (Android SDK jest tylko na GitHubie);
- instalacja na telefonie.

## Dalej
ETAP 5: backtest walk-forward na historii, kalibracja, wpływ kontuzji, waga model/rynek dobrana na danych.
ETAP 6: powiadomienia lokalne, kupony.
ETAP 7: testy na urządzeniu, raport końcowy.
