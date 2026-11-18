# Tryb rynkowy, raport kontuzji NBA, ClubElo — stan (2026-11-18, gałąź `kontuzje-clubelo`, aplikacja v0.6)

## Tryb rynkowy (okazje rynkowe)
- Typ bez modelu, gdy najlepszy kurs jest ≥ 3% wyższy od uczciwego kursu rynku (bukmacher z najniższą marżą ≤ 6%, po jej odjęciu); min. 6 innych bukmacherów, kurs ≤ 15% ponad medianę (filtr błędnych / nieaktualnych kursów), kurs ≤ 4,0, linie połówkowe, > 30 min do startu. Działa we wszystkich ligach z kursami, gdy model nie ma zweryfikowanego typu.
- W aplikacji: znacznik „Okazja rynkowa”, opis i uzasadnienie (kurs vs kurs uczciwy, mediana rynku, minimalny kurs w Polsce po podatku). Przełącznik w Profilu. Statystyki → Backtest pokazuje symulację na historii.
- **Backtest (reguły ustalone z góry, wszystkie sezony):** PL 239 typów, ROI +8,1% (±9,5%), EV wobec zamknięcia +3,9%; La Liga 288, +0,9%, +4,3%; Bundesliga 231, +2,8%, +3,4%; Ekstraklasa 305, +4,8% (plik ma tylko kursy zamknięcia). **Po podatku 12%: od −4,8% do −11,2%.** Wniosek: przewaga wobec linii zamknięcia jest stała, ale w Polsce podatek ją zjada — opłaca się tylko, gdy polski bukmacher da kurs ≥ podanego minimum (lub bez podatku).
- NBA: archiwum ma jeden kurs na mecz — trybu nie da się sprawdzić na historii.

## Raport kontuzji NBA
- Oficjalny PDF ligi (co 15 min), najnowszy z ostatnich 12 h; odczyt tabeli z pozycji słów (pdfplumber), zawijane powody i przejścia stron; zapis jako migawka w `injuries`. Test na prawdziwym raporcie z 18.11.2026 (44 wpisy).
- Aplikacja: nieobecni w meczu NBA (bez przypisań do G League i statusu „Available”), czynnik „Nieobecni” w analizie kursu. Model nie zna wagi zawodników.

## ClubElo
- `api.clubelo.com/RRRR-MM-DD` (CSV). **Stan 18.11.2026: API zwraca 502 z serwerów GitHub, a endpoint Fixtures jest wyłączony.** Pipeline próbuje codziennie; awaria to tylko ostrzeżenie. Gdy wróci — w analizie kursu pojawi się czynnik ClubElo.

## Testy
pytest 55/55, TS 18/18, build APK i backtest na gałęzi: sukces.
