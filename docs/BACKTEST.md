# Backtest walk-forward i kalibracja (ETAP 5)

Wygenerowano automatycznie: 2026-11-18T11:58:15Z (`python -m app.backtest run`, workflow „Backtest i kalibracja”). Nie edytować ręcznie.

## Werdykt

| Rozgrywki | Status | Uzasadnienie |
|---|---|---|
| Premier League | ⏳ w walidacji — typy wyłączone | h2h: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej; totals: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| La Liga | ⏳ w walidacji — typy wyłączone | h2h: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej; totals: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| Bundesliga | ⏳ w walidacji — typy wyłączone | h2h: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej; totals: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| Ekstraklasa | ⏳ w walidacji — typy wyłączone | h2h: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| NBA | ⏳ w walidacji — typy wyłączone | h2h: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej; spreads: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej; totals: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| Liga Mistrzów | ⏳ w walidacji — typy wyłączone | ratingi międzyligowe; brak darmowej historii kursów pucharowych — waga jak w ligach krajowych, walidacja na kursach zbieranych na bieżąco |
| Liga Europy | ⏳ w walidacji — typy wyłączone | ratingi międzyligowe; brak darmowej historii kursów pucharowych — waga jak w ligach krajowych, walidacja na kursach zbieranych na bieżąco |
| Euroliga | — tylko kursy rynku | brak darmowego źródła wyników Euroligi do modelu |

## Metoda

- **Walk-forward, bez wycieku danych.** Model piłkarski (Dixon–Coles) jest dopasowywany co tydzień (poniedziałek rano), tylko na meczach rozegranych wcześniej (okno 2 lata), i prognozuje mecze kolejnych 7 dni. NBA: codziennie przed meczami, okno ~1,5 sezonu.
- **Rynek jako punkt odniesienia.** Prawdopodobieństwo rynku = kursy referencyjne bez marży: Pinnacle przed meczem; gdy Pinnacle znika z plików (od 2025) — Betfair Exchange; w ostateczności średnia rynku. Ekstraklasa ma w pliku tylko kursy zamknięcia (najmocniejszy rynek → test ostrożny). NBA: konsensus zamknięcia (sportsbookreviewsonline), handicap i suma przy kursie 1,909.
- **Okres strojenia i okres testowy.** Piłka: strojenie do 30.06.2025, test od 1.07.2025 (sezon 2025/26 i bieżący). NBA: strojenie 2019/20–2021/22, test 2022/23. Na okresie testowym niczego się nie dobiera.
- **Dobór na okresie strojenia:** zanik czasowy modelu (XI) — minimalny log-loss surowego modelu; waga model/rynek — minimalny log-loss mieszanki (siatka co 0,05); skala niepewności — średnia rozbieżność model–rynek ≈ 1 półszerokość przedziału; progi min. EV 2%, 3%, 4%, 5%, 6%, 8% i maks. rozbieżności 5%, 8%, 12% — maksimum (ROI − 1 błąd standardowy), min. 60 typów.
- **Symulacja zakładów = ten sam kod co na żywo** (`engine.evaluate.price_market`): ta sama ocena jakości, progi, limit kursu 5,0, maks. 2 typy na mecz. Kurs wzięty = najlepszy kurs rynku (maksimum z plików, wartości odstające >25% ponad średnią zastąpione średnią). Wyniki pokazane też przy kursach średnich i po podatku 12%.
- **Reguła walidacji (ustalona przed obejrzeniem wyników):** rynek ligi dostaje typy tylko, jeśli waga modelu ≥ 0.10, na okresie testowym mieszanka ma niższy log-loss niż sam rynek z prawdopodobieństwem bootstrap ≥ 0.80, było ≥ 30 typów i ROI ≥ 0. W przeciwnym razie model jest pokazywany, ale typy są wyłączone (status „w walidacji”).

## Piłka nożna

Zanik czasowy (log-loss 1X2 na okresie strojenia): XI=0.001: 1,01023, XI=0.0019: 1,01018, XI=0.0035: 1,01175 → wybrano **XI=0.0019**.

### Premier League

Sezony: 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026. Wiersze (rynek × mecz): strojenie 3984, test 960. Źródła kursu referencyjnego: Avg, BFE, P, PS. Progi: min. EV 2%, maks. rozbieżność model–rynek 12%.

| Rynek | Waga modelu | Skala niepewności | Log-loss: model / rynek / mieszanka (test) | Δ vs rynek (test) | P(lepszy) | Typy (test) | ROI (test) | Status |
|---|---|---|---|---|---|---|---|---|
| 1X2 / zwycięzca | 0,00 | 2,03 | 1,0440 / 1,0155 / 1,0155 | 0,00000 | 0,00 | 3 | -20,7% | ⏳ w walidacji optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| suma (O/U) | 0,00 | 1,34 | 0,7076 / 0,6904 / 0,6904 | 0,00000 | 0,00 | 3 | -100,0% | ⏳ w walidacji optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |

- Strojenie: 10 typów, trafność 70,0%, średni kurs 2,17, ROI +51,7% (±34,4%), przy kursach średnich +41,0%, po podatku 12% +33,5%, CLV +2,8%, EV wobec linii zamknięcia +4,4%.
- Test: 6 typów, trafność 16,7%, średni kurs 2,35, ROI -60,3% (±39,7%), przy kursach średnich -64,5%, po podatku 12% -65,1%, CLV +10,0%, EV wobec linii zamknięcia +6,7%.

### La Liga

Sezony: 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026. Wiersze (rynek × mecz): strojenie 4020, test 998. Źródła kursu referencyjnego: Avg, BFE, P, PS. Progi: min. EV 2%, maks. rozbieżność model–rynek 12%.

| Rynek | Waga modelu | Skala niepewności | Log-loss: model / rynek / mieszanka (test) | Δ vs rynek (test) | P(lepszy) | Typy (test) | ROI (test) | Status |
|---|---|---|---|---|---|---|---|---|
| 1X2 / zwycięzca | 0,00 | 0,91 | 0,9777 / 0,9522 / 0,9522 | 0,00000 | 0,00 | 1 | +200,0% | ⏳ w walidacji optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| suma (O/U) | 0,00 | 1,13 | 0,6807 / 0,6645 / 0,6645 | 0,00000 | 0,00 | 0 | — | ⏳ w walidacji optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |

- Strojenie: 11 typów, trafność 45,5%, średni kurs 2,32, ROI +7,4% (±38,1%), przy kursach średnich -1,4%, po podatku 12% -5,5%, CLV +1,3%, EV wobec linii zamknięcia +3,3%.
- Test: 1 typów, trafność 100,0%, średni kurs 3,00, ROI +200,0% (±—), przy kursach średnich +149,0%, po podatku 12% +164,0%, CLV +20,0%, EV wobec linii zamknięcia +16,9%.

### Bundesliga

Sezony: 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026. Wiersze (rynek × mecz): strojenie 3224, test 774. Źródła kursu referencyjnego: Avg, BFE, P, PS. Progi: min. EV 2%, maks. rozbieżność model–rynek 12%.

| Rynek | Waga modelu | Skala niepewności | Log-loss: model / rynek / mieszanka (test) | Δ vs rynek (test) | P(lepszy) | Typy (test) | ROI (test) | Status |
|---|---|---|---|---|---|---|---|---|
| 1X2 / zwycięzca | 0,00 | 0,89 | 1,0190 / 0,9550 / 0,9550 | 0,00000 | 0,00 | 1 | -100,0% | ⏳ w walidacji optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| suma (O/U) | 0,00 | 1,04 | 0,6701 / 0,6292 / 0,6292 | 0,00000 | 0,00 | 0 | — | ⏳ w walidacji optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |

- Strojenie: 5 typów, trafność 60,0%, średni kurs 2,36, ROI +53,0% (±63,2%), przy kursach średnich +40,2%, po podatku 12% +34,6%, CLV +2,2%, EV wobec linii zamknięcia +5,1%.
- Test: 1 typów, trafność 0,0%, średni kurs 3,00, ROI -100,0% (±—), przy kursach średnich -100,0%, po podatku 12% -100,0%, CLV +0,0%, EV wobec linii zamknięcia +14,7%.

### Ekstraklasa

Sezony: 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026. Wiersze (rynek × mecz): strojenie 1553, test 430. Źródła kursu referencyjnego: AvgC, BFEC, PSC. Progi: min. EV 2%, maks. rozbieżność model–rynek 12%.

| Rynek | Waga modelu | Skala niepewności | Log-loss: model / rynek / mieszanka (test) | Δ vs rynek (test) | P(lepszy) | Typy (test) | ROI (test) | Status |
|---|---|---|---|---|---|---|---|---|
| 1X2 / zwycięzca | 0,00 | 0,95 | 1,0805 / 1,0449 / 1,0449 | 0,00000 | 0,00 | 4 | +73,5% | ⏳ w walidacji optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |

- Strojenie: 49 typów, trafność 38,8%, średni kurs 2,43, ROI -5,6% (±17,4%), przy kursach średnich -15,7%, po podatku 12% -16,9%, CLV +0,0%, EV wobec linii zamknięcia +7,4%.
- Test: 4 typów, trafność 75,0%, średni kurs 2,38, ROI +73,5% (±59,8%), przy kursach średnich +62,2%, po podatku 12% +52,7%, CLV +0,0%, EV wobec linii zamknięcia +9,5%.

## NBA

Mecze z kursami: 4301. Zanik: XI=0.004: 0,64255, XI=0.008: 0,63914, XI=0.015: 0,64146 → **XI=0.008**. Uwaga: spread/total: -110 (1.909) assumed.

| Rynek | Waga modelu | Skala niepewności | Log-loss: model / rynek / mieszanka (test) | Δ vs rynek (test) | P(lepszy) | Typy (test) | ROI (test) | Status |
|---|---|---|---|---|---|---|---|---|
| 1X2 / zwycięzca | 0,00 | 1,21 | 0,6473 / 0,6390 / 0,6390 | 0,00000 | 0,00 | 0 | — | ⏳ w walidacji optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| handicap | 0,00 | 1,21 | 0,7120 / 0,6931 / 0,6931 | 0,00000 | 0,00 | 0 | — | ⏳ w walidacji optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| suma (O/U) | 0,00 | 1,20 | 0,7240 / 0,6931 / 0,6931 | 0,00000 | 0,00 | 0 | — | ⏳ w walidacji optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |

- Strojenie: brak typów.
- Test: brak typów.

Zmęczenie i terminarz (dni odpoczynku, back-to-back, podróż): **nie poprawiły modelu — wyłączone**. Log-loss surowego modelu na strojeniu bez / z: 1X2 0,63914 / 0,63880, handicap 0,71956 / 0,72156. Efekty (punkty różnicy dla gospodarza): dzień odpoczynku więcej -0,08, gospodarz b2b -2,03, gość b2b 2,17, 1000 km podróży gościa więcej 0,28.

Kontrola rozkładu (test): w ±1σ różnicy punktów 69%, sumy 69% (oczekiwane ~68%); odch. std z-score: różnica 0,98, suma 1,01; średni błąd sumy 3,2 pkt.

## Puchary (Liga Mistrzów, Liga Europy): ratingi międzyligowe

Model łączny: 26504 meczów ligowych z 21 lig krajowych (football-data.co.uk) + 2639 meczów pucharowych (API-Football 2022–2024 i bieżący sezon z bazy), 673 drużyn.

Test: 2024/25 (wszystkie fazy, model z danych sprzed 1.07.2024), 461 meczów z drużynami o wystarczającej historii. Log-loss 1X2: model **0,9921**, punkt odniesienia (częstości 1/X/2 z meczów pucharowych 2022-2024) 1,0350.

| Prognoza (średnio) | Wynik (częstość) | Liczba |
|---|---|---|
| 7% | 4% | 52 |
| 16% | 20% | 205 |
| 25% | 24% | 511 |
| 34% | 34% | 199 |
| 44% | 50% | 172 |
| 55% | 44% | 118 |
| 64% | 62% | 71 |
| 75% | 74% | 39 |

Darmowe źródła nie mają historii kursów pucharowych, więc przewagi nad rynkiem nie da się jeszcze sprawdzić: model jest pokazywany w aplikacji, typy pozostają wyłączone, a kursy zbierane codziennie posłużą do walidacji.

## Tryb rynkowy (bez modelu)

Typ = najlepszy kurs rynku co najmniej 3% powyżej kursu uczciwego (kurs referencyjny po odjęciu marży), kurs ≤ 4,0, najwyżej 15% ponad kurs średni, linie połówkowe. Reguły ustalone z góry (nic nie dobierano na danych), więc liczą się wszystkie sezony. Kluczowa miara: EV wobec linii zamknięcia (czy kurs wzięty był lepszy od uczciwego kursu tuż przed meczem) — mniej zależna od szczęścia niż ROI.

| Liga | Typy | Trafność | Śr. kurs | ROI (kurs najlepszy) | ROI po podatku | EV wobec zamknięcia | Test od 1.07.2025: typy / ROI |
|---|---|---|---|---|---|---|---|
| Premier League | 239 | 38,1% | 3,08 | +8,1% (±9,5%) | -4,8% | +3,9% | 11 / +5,7% |
| La Liga | 288 | 33,3% | 3,16 | +0,9% (±8,7%) | -11,2% | +4,3% | 8 / -12,8% |
| Bundesliga | 231 | 31,6% | 3,32 | +2,8% (±10,3%) | -9,5% | +3,4% | 10 / -30,3% |
| Ekstraklasa | 305 | 38,7% | 2,84 | +4,8% (±8,0%) | -7,8% | +5,2% | 26 / -3,5% |

NBA: archiwum ma jeden kurs na mecz (konsensus), więc trybu rynkowego nie da się sprawdzić na historii — w aplikacji działa na bieżących kursach wielu bukmacherów.

## Niskie kursy: czy to pułapka?

Wszystkie mecze z kursami (bez modelu). Kurs średni rynku przed meczem; „wygrane” = jak często selekcja w tym przedziale kursu faktycznie wygrała; zwrot = wynik obstawiania każdej takiej selekcji po 1 zł.

**Premier League** (2760 meczów, football-data.co.uk, kurs średni przed meczem):

| Kurs | Liczba | Wygrane (95% przedział) | Zakładał kurs | bez marży | Zwrot przy kursie średnim | przy najlepszym | po podatku 12% |
|---|---|---|---|---|---|---|---|
| 1,01–1,15 | 49 | 87,8% (76%–94%) | 90,1% | 87,0% | -2,7% | -0,7% | -14,4% |
| 1,15–1,25 | 127 | 79,5% (72%–86%) | 83,6% | 80,6% | -5,1% | -2,9% | -16,5% |
| 1,25–1,35 | 159 | 72,3% (65%–79%) | 77,1% | 74,3% | -6,2% | -3,9% | -17,4% |
| 1,35–1,45 | 210 | 69,0% (62%–75%) | 71,8% | 69,1% | -3,8% | -1,1% | -15,3% |
| 1,45–1,60 | 291 | 68,0% (62%–73%) | 65,8% | 63,4% | +3,3% | +6,1% | -9,1% |
| 1,60–1,80 | 427 | 55,5% (51%–60%) | 59,1% | 56,9% | -5,7% | -3,1% | -17,0% |

**La Liga** (2779 meczów, football-data.co.uk, kurs średni przed meczem):

| Kurs | Liczba | Wygrane (95% przedział) | Zakładał kurs | bez marży | Zwrot przy kursie średnim | przy najlepszym | po podatku 12% |
|---|---|---|---|---|---|---|---|
| 1,15–1,25 | 95 | 84,2% (76%–90%) | 83,5% | 80,1% | +0,9% | +3,3% | -11,2% |
| 1,25–1,35 | 118 | 74,6% (66%–82%) | 77,0% | 74,0% | -3,2% | -0,6% | -14,8% |
| 1,35–1,45 | 156 | 78,2% (71%–84%) | 71,7% | 69,0% | +9,2% | +12,5% | -3,9% |
| 1,45–1,60 | 245 | 70,6% (65%–76%) | 65,9% | 63,5% | +7,2% | +10,4% | -5,7% |
| 1,60–1,80 | 418 | 56,2% (51%–61%) | 59,1% | 56,9% | -4,9% | -2,0% | -16,3% |

**Bundesliga** (2223 meczów, football-data.co.uk, kurs średni przed meczem):

| Kurs | Liczba | Wygrane (95% przedział) | Zakładał kurs | bez marży | Zwrot przy kursie średnim | przy najlepszym | po podatku 12% |
|---|---|---|---|---|---|---|---|
| 1,01–1,15 | 50 | 84,0% (71%–92%) | 90,8% | 87,4% | -7,4% | -5,1% | -18,5% |
| 1,15–1,25 | 112 | 78,6% (70%–85%) | 83,5% | 80,1% | -5,7% | -3,1% | -17,0% |
| 1,25–1,35 | 110 | 70,0% (61%–78%) | 77,2% | 74,1% | -9,3% | -6,7% | -20,2% |
| 1,35–1,45 | 153 | 77,1% (70%–83%) | 71,7% | 68,9% | +7,4% | +10,6% | -5,5% |
| 1,45–1,60 | 220 | 62,3% (56%–68%) | 65,8% | 63,2% | -5,5% | -2,5% | -16,8% |
| 1,60–1,80 | 315 | 57,5% (52%–63%) | 59,0% | 56,6% | -2,5% | +0,5% | -14,2% |

**Ekstraklasa** (2190 meczów, football-data.co.uk, kurs średni przed meczem (zamknięcie)):

| Kurs | Liczba | Wygrane (95% przedział) | Zakładał kurs | bez marży | Zwrot przy kursie średnim | przy najlepszym | po podatku 12% |
|---|---|---|---|---|---|---|---|
| 1,25–1,35 | 47 | 70,2% (56%–81%) | 76,5% | 72,9% | -8,2% | -4,5% | -19,2% |
| 1,35–1,45 | 63 | 68,2% (56%–78%) | 71,4% | 67,7% | -4,7% | -0,5% | -16,1% |
| 1,45–1,60 | 163 | 60,7% (53%–68%) | 65,6% | 62,1% | -7,4% | -3,9% | -18,5% |
| 1,60–1,80 | 289 | 56,4% (51%–62%) | 58,9% | 55,9% | -4,4% | -0,0% | -15,8% |

**NBA** (4300 meczów, sportsbookreviewsonline, moneyline zamknięcia):

| Kurs | Liczba | Wygrane (95% przedział) | Zakładał kurs | bez marży | Zwrot przy kursie średnim | przy najlepszym | po podatku 12% |
|---|---|---|---|---|---|---|---|
| 1,01–1,15 | 402 | 85,1% (81%–88%) | 91,0% | 87,3% | -6,6% | -6,6% | -17,8% |
| 1,15–1,25 | 430 | 78,1% (74%–82%) | 83,5% | 80,5% | -6,4% | -6,4% | -17,6% |
| 1,25–1,35 | 612 | 71,4% (68%–75%) | 77,2% | 74,5% | -7,5% | -7,5% | -18,6% |
| 1,35–1,45 | 572 | 68,2% (64%–72%) | 71,9% | 69,3% | -5,1% | -5,1% | -16,5% |
| 1,45–1,60 | 862 | 64,0% (61%–67%) | 65,7% | 63,7% | -2,6% | -2,6% | -14,3% |
| 1,60–1,80 | 983 | 57,3% (54%–60%) | 59,2% | 57,1% | -3,3% | -3,3% | -14,9% |

## Ograniczenia

- Kurs „najlepszy rynku” z plików to maksimum z kilkudziesięciu bukmacherów — w praktyce trudniej osiągalny niż średnia; dlatego raport podaje też ROI przy kursach średnich i po podatku 12%.
- NBA: archiwum kursów kończy się na sezonie 2022/23; spread i suma bez kursów (przyjęto 1,909).
- Brak danych o kontuzjach i składach w darmowych źródłach — model ich nie widzi, co ogranicza jego przewagę nad rynkiem.
- Mała próba = duża wariancja: ROI z kilkudziesięciu typów nie dowodzi przewagi. Decyduje przede wszystkim log-loss (właściwa reguła oceny) na okresie testowym.
