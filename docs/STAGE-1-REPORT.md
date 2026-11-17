# Raport: ETAP 1 i ETAP 2

Data: 2026-11-17. Wersja: 0.1.0.

## Co zbudowano

Frontend PWA działający na danych DEMO. Każdy ekran ma baner „TRYB DEMO”, a każda karta znacznik DEMO.

| Ekran | Zawartość |
|---|---|
| Start | logo, data, powiadomienia (arkusz), status danych + odświeżanie, podsumowanie (analizy, value bety, śr. EV, wycofane), okazja dnia, TOP rekomendacje, nadchodzące mecze, ostatnie aktualizacje |
| Typy | maks. 10; filtry: piłka/kosz, ryzyko niskie/średnie/wysokie; sortowanie: ocena, największe value, najwyższe prawdopodobieństwo, kurs vs prawdopodobieństwo; rozwijane uzasadnienie za/przeciw |
| Mecze | widok piłki / koszykówki / wszystkie, zakres Dziś/Jutro/3/7 dni, wyszukiwarka, filtr lig, „tylko z typem”, sortowanie wg atrakcyjności lub godziny, **kalendarz** 8 dni |
| Analiza meczu | nagłówek z formą, 5 zakładek: Analiza (najlepszy typ, alternatywy, wycofane typy, prawdopodobieństwa model vs rynek, ryzyka, status źródeł danych), Rynki (wszystkie rynki z marżą i EV, powód odrzucenia, rynki niedostępne), Kursy (porównanie bukmacherów, wykres ruchu kursu), Forma i statystyki (forma 8 meczów, porównanie statystyk, H2H), Składy (absencje, składy z ich statusem) |
| Statystyki | rozdzielnie: Rekomendacje i Backtest; zysk, ROI/yield, skuteczność, śr. kurs, CLV, krzywa zysku, kalibracja + Brier, wyniki wg dyscypliny/rynku/ryzyka, ostrzeżenie o małej próbie |
| Historia typów | grupowana po dniach, filtry (trafione/nietrafione/oczekujące), kurs otwarcia → zamknięcia, wynik, zysk |
| Profil | progi rekomendacji (zapisywane), bukmacherzy, powiadomienia, status źródeł API, odpowiedzialna gra (jednostka, limit), instalacja PWA |

PWA ma manifest, ikony (w tym maskable), Service Worker (powłoka aplikacji: stale-while-revalidate; `/api` tylko z sieci, żeby nieaktualne kursy nie były podawane po cichu) i obsługę Web Push przygotowaną pod ETAP 6.

## Wyniki testów

### Testy jednostkowe (matematyka kursów): 11 ZALICZONYCH / 0 NIEZALICZONYCH
p implikowane, marża 1X2, kursy bez marży, EV (przykład z briefu: p = 0,82 przy kursie 1,35 daje EV +10,7%), EV = 0 przy kursie godziwym, walidacja wejścia, Kelly, CLV, najlepszy kurs.

### Testy funkcjonalne (Playwright, emulacja Pixel 7, Chrome): 15 ZALICZONYCH / 0 NIEZALICZONYCH
1. Dashboard renderuje KPI i okazję dnia: ZALICZONY
2. Baner DEMO widoczny na każdym ekranie: ZALICZONY
3. Dolna nawigacja: 5 pozycji: ZALICZONY
4. Powiadomienia: otwieranie/zamykanie, znika licznik: ZALICZONY
5. Typy: maks. 10, filtr koszykówki: ZALICZONY
6. Typy: pusty filtr pokazuje komunikat „Brak zakładów spełniających…”: ZALICZONY
7. Typy: rozwinięcie uzasadnienia: ZALICZONY
8. Mecze: zakresy dat i wyszukiwarka: ZALICZONY
9. Mecze: kalendarz i przełączanie dni: ZALICZONY
10. Analiza meczu: zakładki, rynki z marżą, kursy, składy: ZALICZONY
11. Statystyki: Rekomendacje/Backtest i Historia: ZALICZONY
12. Ustawienia zawężają listę typów i zostają zapisane po odświeżeniu: ZALICZONY
13. PWA: manifest, ikony, rejestracja Service Workera: ZALICZONY
14. Offline: aplikacja ładuje się z cache: ZALICZONY
15. Czas do wyrenderowania dashboardu < 1,5 s (localhost): ZALICZONY

### Układ responsywny: 36 ZALICZONYCH / 0 NIEZALICZONYCH
12 widoków × 3 szerokości (360, 390, 412 px). Żaden nie ma poziomego przepełnienia ani błędów w konsoli.

### Naprawione błędy (wykryte podczas testów)
- **Krytyczny:** dashboard się wykrzaczał, gdy podsumowanie jeszcze się ładowało (odwołanie do `undefined`). Naprawione, potwierdzone ponownym testem.
- Podwójna szansa była źle wyceniana (normalizacja do 1 przy selekcjach, które się nakładają), co dawało zawyżone EV. Naprawione.
- Generator DEMO wypluwał za dużo „okazji”. Zmniejszyłem szum, dodałem twardy limit kursu 5,00 i przekalibrowałem ocenę.
- Głęboki link do kalendarza nie przełączał widoku przy tej samej trasie. Naprawione.
- Zwinięte uzasadnienia były osiągalne z klawiatury i czytnika ekranu (dodane `inert`).
- Kosmetyka: polskie wielkie litery w datach, minus w handicapach, odmiana liczebników, kolor wykresu kursu, układ okazji dnia przy 360 px.

### NIEWYKONANE (ograniczenia środowiska)
- `tsc --noEmit` dla plików React: w sandboxie brak `@types/react`. Moduły bez Reacta przechodzą `tsc --strict` bez błędów. Pełny typecheck uruchamia `npm run build`.
- Instalacja PWA na fizycznym Androidzie: wymaga Twojego telefonu i hostingu z HTTPS. Do zrobienia w ETAPIE 7, albo wcześniej przez `npm run dev -- --host` w sieci lokalnej (bez instalacji PWA, bo ona wymaga HTTPS).
- Testy backendu, API, bezpieczeństwa i obciążenia: dotyczą ETAPÓW 3–7.

## Znane ograniczenia ETAPU 1
- Wszystkie dane są fikcyjne. Nazwy drużyn są prawdziwe, ale ratingi, kursy, kontuzje i statystyki zostały wygenerowane. Zawodnicy są opisani pozycją i numerem, bez prawdziwych nazwisk.
- Kupony (moduł opcjonalny): ETAP 6.
- Logowanie i rejestracja: ETAP 3.

## Dalej: ETAP 3
FastAPI + PostgreSQL + Redis + Celery: schemat bazy (`docs/ARCHITECTURE.md` §3), rejestracja i logowanie (Argon2 + JWT w httpOnly cookie), endpointy zgodne z `types/domain.ts`, `HttpProvider` w miejsce `DemoProvider`, Docker Compose.
