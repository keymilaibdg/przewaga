# Analiza kursu i zmęczenie NBA — stan (2026-11-18, gałąź `analiza-kursu`)

## Po co
Użytkownik wielokrotnie przegrywał na kursach 1,3–1,4 i chciał w aplikacji szczegółowego uzasadnienia: skąd taki kurs, czy jest „pułapką”, czy się opłaca, jakie niesie ryzyko — także gdy obie drużyny mają serie porażek.

## Co zbudowano
- **Karta „Analiza kursu”** w analizie meczu (zakładka Analiza), dla każdej selekcji 1X2 / moneyline, domyślnie dla faworyta: werdykt (Warto rozważyć / Bez przewagi / Nieopłacalne) z punktami, „Dlaczego taki kurs?”, tabela czynników obu drużyn, „Skąd się wziął kurs”, „Historia kursów” w danym przedziale, „Opłacalność” (na 100 zł po podatku), „Ryzyko”.
- **Historia kursów** (`pipeline/app/price_buckets.json`, generowana przez backtest): PL/La Liga/Bundesliga 2019/20–2026/27, Ekstraklasa (kursy zamknięcia), NBA 2019/20–2022/23 — razem ok. 14 tys. meczów.
- **Zmęczenie i terminarz NBA** (`models/schedule.py`): dni przerwy, back-to-back, podróż (km między halami), mecze w 7 dni. Backtest 2019–2023: efekt back-to-back ok. 2 pkt różnicy, ale **nie poprawił prognozy** (rynek już to uwzględnia) — w modelu wyłączone, w analizie pokazywane.

## Najważniejsze wyniki historii kursów (kurs średni rynku)
| Liga, kurs 1,25–1,35 | Wygrane | Kurs bez marży zakładał | Zwrot | Po podatku 12% |
|---|---|---|---|---|
| Premier League | 72,3% | 74,3% | −6,2% | −17,4% |
| Bundesliga | 70,0% | 74,1% | −9,3% | −20,2% |
| NBA | 71,4% | 74,5% | −7,5% | −18,6% |

Wniosek: niskie kursy są wyceniane zwykle trafnie albo minimalnie przeceniają faworyta (w NBA na granicy istotności). Strata przy grze na „pewniaki” to przede wszystkim marża i 12% podatek: przy kursie 1,30 po podatku trzeba by wygrywać ok. 87% zakładów, a takie selekcje wygrywają ok. 72%.

## Testy
pytest 50/50 (w tym: kontekst terminarza, odzyskanie efektu back-to-back na danych syntetycznych, przedziały kursów, prawdopodobieństwo straty po serii, analiza kursu w opublikowanym JSON), testy TS 18/18, build APK na gałęzi.
