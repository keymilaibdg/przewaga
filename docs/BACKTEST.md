# Backtest walk-forward i kalibracja (ETAP 5)

Wygenerowano automatycznie: 2026-11-18T09:49:33Z (`python -m app.backtest run`, workflow „Backtest i kalibracja”). Nie edytować ręcznie.

## Werdykt

| Rozgrywki | Status | Uzasadnienie |
|---|---|---|
| Premier League | ⏳ w walidacji — typy wyłączone | h2h: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej; totals: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| La Liga | ⏳ w walidacji — typy wyłączone | h2h: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej; totals: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| Bundesliga | ⏳ w walidacji — typy wyłączone | h2h: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej; totals: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| Ekstraklasa | ⏳ w walidacji — typy wyłączone | h2h: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| NBA | ⏳ w walidacji — typy wyłączone | h2h: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej; spreads: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej; totals: optymalna waga modelu 0.00 — rynek bez marży prognozuje lepiej |
| Liga Mistrzów | ⏳ w walidacji — typy wyłączone | ratingi międzyligowe; brak darmowej historii kursów pucharowych — walidacja na kursach zbieranych na bieżąco |
| Liga Europy | ⏳ w walidacji — typy wyłączone | ratingi międzyligowe; brak darmowej historii kursów pucharowych — walidacja na kursach zbieranych na bieżąco |
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

Kontrola rozkładu (test): w ±1σ różnicy punktów 69%, sumy 69% (oczekiwane ~68%); odch. std z-score: różnica 0,98, suma 1,01; średni błąd sumy 3,2 pkt.

## Puchary (Liga Mistrzów, Liga Europy): ratingi międzyligowe

Model łączny: 26504 meczów ligowych z 21 lig krajowych (football-data.co.uk) + 2639 meczów pucharowych (API-Football 2022–2024 i bieżący sezon z bazy), 682 drużyn.

Test: 2024/25 (wszystkie fazy, model z danych sprzed 1.07.2024), 431 meczów z drużynami o wystarczającej historii. Log-loss 1X2: model **0,9994**, punkt odniesienia (częstości 1/X/2 z meczów pucharowych 2022-2024) 1,0324.

| Prognoza (średnio) | Wynik (częstość) | Liczba |
|---|---|---|
| 6% | 4% | 47 |
| 16% | 22% | 186 |
| 25% | 24% | 485 |
| 34% | 35% | 190 |
| 45% | 50% | 162 |
| 55% | 42% | 110 |
| 64% | 64% | 63 |
| 75% | 71% | 34 |

Darmowe źródła nie mają historii kursów pucharowych, więc przewagi nad rynkiem nie da się jeszcze sprawdzić: model jest pokazywany w aplikacji, typy pozostają wyłączone, a kursy zbierane codziennie posłużą do walidacji.

## Ograniczenia

- Kurs „najlepszy rynku” z plików to maksimum z kilkudziesięciu bukmacherów — w praktyce trudniej osiągalny niż średnia; dlatego raport podaje też ROI przy kursach średnich i po podatku 12%.
- NBA: archiwum kursów kończy się na sezonie 2022/23; spread i suma bez kursów (przyjęto 1,909).
- Brak danych o kontuzjach i składach w darmowych źródłach — model ich nie widzi, co ogranicza jego przewagę nad rynkiem.
- Mała próba = duża wariancja: ROI z kilkudziesięciu typów nie dowodzi przewagi. Decyduje przede wszystkim log-loss (właściwa reguła oceny) na okresie testowym.
