# Przewaga — architektura systemu

Osobisty asystent analityczny: piłka nożna + koszykówka. Cel: wskazywać wyłącznie zakłady z dodatnią wartością oczekiwaną (EV > 0), z jawną niepewnością, albo jasno rekomendować odpuszczenie meczu.

Status dokumentu: wersja 3 (2026-11-17, wariant bezkosztowy, aplikacja APK). Wszystko oznaczone **[DO WERYFIKACJI]** zostanie potwierdzone w ETAPIE 4 (dostępność API, limity, ceny, warunki licencyjne).

---

## 1. Decyzje technologiczne

**Decyzja z 2026-11-17: wariant bezkosztowy (0 zł).** Brak własnego serwera, bazy PostgreSQL, Redis i Celery. Zastępują je zaplanowane zadania GitHub Actions oraz pliki danych w repozytorium. Rezygnacja z pierwotnego stosu jest świadomym uproszczeniem względem briefu. Skutki opisuje sekcja 1a.

| Warstwa | Wybór | Uzasadnienie |
|---|---|---|
| Frontend | React 19 + TypeScript + Tailwind CSS v4 (bez zmian) | Wspólny interfejs dla APK i wersji web. |
| Aplikacja | **APK na Androida** (Capacitor) z tym samym interfejsem React. Budowany za darmo w GitHub Actions, publikowany w GitHub Releases. Wersja web (PWA) pozostaje dostępna z tego samego kodu. | Decyzja użytkownika z 2026-11-17: instalacja z pliku .APK, wysyłanie znajomym linkiem. |
| Dystrybucja danych | Publiczne repozytorium GitHub, gałąź `data` (tylko najnowsze JSON, nadpisywane), pobierane przez aplikację z raw.githubusercontent.com | Jedno darmowe konto (GitHub), bez Cloudflare. Typy są publiczne pod adresem repozytorium (decyzja użytkownika). |
| „Backend” | **Python w GitHub Actions** uruchamiany cyklicznie (cron) | Pobiera dane z API, liczy modele i zapisuje wyniki jako JSON. Plan Free daje 2000 min/mies. dla repozytorium prywatnego. Publiczne repozytorium nie ma limitu minut. |
| Dane i historia | SQLite + JSON w repozytorium (historia typów, migawki kursów, wyniki) | Bez płatnej bazy. Plikowa baza wystarczy dla jednego użytkownika. Historia nigdy nie jest kasowana (append-only). |
| Klucze API | GitHub Secrets | Nie trafiają do aplikacji ani do kodu (repozytorium jest publiczne, sekrety są szyfrowane). |
| Podpis APK | Stały klucz w GitHub Secrets (`ANDROID_KEYSTORE_B64`) | Aktualizacje instalują się na poprzednią wersję. Bez klucza powstaje APK debug. |
| Modele | NumPy / SciPy w zadaniu Pythona | Bez zmian względem planu. |
| Powiadomienia | ETAP 6: powiadomienia lokalne w APK po pobraniu nowych analiz | Bez serwera i bez płatnych usług push. |
| Dostęp | Bez logowania: aplikacja i typy są wspólne dla każdego, kto ma APK; ustawienia trzymane lokalnie na telefonie | Konsekwencja publicznego repozytorium. Logowanie z briefu jest świadomie pominięte (brak serwera). |

### 1a. Konsekwencje wariantu darmowego

- **Częstotliwość aktualizacji ogranicza darmowy limit danych, nie hosting.** football-data.org Free: 10 zapytań/min, bieżący sezon; balldontlie Free: 5 zapytań/min. The Odds API Starter: 500 kredytów/mies. (zapytanie = rynki × regiony). W praktyce kursy odświeżane są 1–3 razy dziennie dla wybranych lig, a nie co kilka minut.
- **Zakres lig (decyzja użytkownika):** Premier League, La Liga, Bundesliga, Liga Mistrzów, Liga Europy, Ekstraklasa, NBA, Euroliga. Pokrycie kursami w darmowym planie do potwierdzenia przy pierwszym uruchomieniu.
- **xG i polscy bukmacherzy:** brak w darmowych planach albo niezweryfikowane. Model działa na bramkach i statystykach, a aplikacja wyraźnie pokazuje brak xG.
- **Offline:** aplikacja przechowuje ostatnie pobrane dane i oznacza je jako „Offline”. Nie przełącza się po cichu na dane DEMO.
- **Podatek 12% od stawki (PL):** aplikacja podaje minimalny kurs u legalnego polskiego bukmachera, przy którym EV pozostaje dodatnie.
- **Harmonogramy GitHub Actions** mogą się opóźniać o kilka–kilkanaście minut. Ponowne przeliczenie przed meczem odbywa się więc „ok. 1–2 h przed”, a nie co do minuty.
- Wszystko jest przygotowane pod późniejsze przejście na płatny plan danych: wystarczy zmienić klucz, bez przepisywania kodu.

## 2. Moduły

```
przewaga/
├── frontend/                 interfejs React (APK przez Capacitor + wersja web)
│   ├── src/types/domain.ts   kontrakt danych współdzielony z pipeline
│   ├── src/api/              DemoProvider (DEMO) / StaticDataProvider (dane live z JSON, kopia offline)
│   ├── src/lib/odds.ts       matematyka kursów (implikowane p, marża, EV, podatek 12%) + testy
│   ├── src/components/       design system: ui/, charts/, layout/, match/
│   ├── src/pages/            ekrany
│   ├── capacitor.config.json konfiguracja aplikacji Android; assets/ = ikony i ekran startowy
│   └── tests/e2e/            testy Playwright: DEMO, live, APK, układ ekranów
├── pipeline/                 Python uruchamiany w GitHub Actions
│   ├── app/providers/        football-data.org, football-data.co.uk (CSV), balldontlie, The Odds API, klient HTTP z budżetem; API-SPORTS tylko do backtestów 2022–2024
│   ├── app/teams.py          jedna tożsamość drużyny między źródłami (tabela team_aliases)
│   ├── app/ingest.py         zapis do SQLite (kursy append-only)
│   ├── app/matching.py       dopasowanie meczów między źródłami
│   ├── app/models/           Dixon–Coles (piłka), ratingi (koszykówka)
│   ├── app/engine/           wycena rynków, EV, ocena jakości, ryzyko
│   ├── app/analysis.py       cykl życia typów, wycofywanie, rozliczanie, CLV
│   ├── app/publish.py        eksport JSON dla aplikacji
│   ├── app/cli.py            punkt wejścia (run --kind morning|afternoon, status)
│   └── tests/                pytest + symulowane API (fake_api.py)
└── .github/workflows/        update.yml (dane), android.yml (APK), tests.yml
```

**Zasada kluczowa:** frontend nigdy nie liczy prognoz. Wyświetla to, co policzył pipeline (prawdopodobieństwo, przedział, EV, ocenę). `lib/odds.ts` służy do formatowania i kontroli spójności, a jego wzory są lustrzanym odbiciem `pipeline/app/engine/odds.py` (te same przypadki testowe w obu).

## 3. Model danych (skrót)

- `league`, `team`, `player` + `external_ids` (mapowanie ID między dostawcami).
- `event` (sport, liga, drużyny, `kickoff_utc`, status, wynik) — unikalność po (liga, drużyny, data ±36h) do deduplikacji.
- `odds_snapshot` (event, rynek, linia, selekcja, bukmacher, kurs, `captured_at`) — append-only → historia ruchów kursu, kurs zamknięcia, CLV.
- `team_stats_snapshot`, `injury`, `lineup` — zawsze z `source` i `fetched_at`.
- `prediction` (event, rynek, selekcja, p, p_low, p_high, model_version, `features_as_of`).
- `recommendation` (prediction, kurs i bukmacher w chwili publikacji, EV, ocena jakości, ryzyko, uzasadnienia, status: aktywna / wycofana / rozliczona) — **nigdy nie usuwana**.
- `settlement` (wynik, zysk w jednostkach, kurs zamknięcia, CLV).
- `backtest_run` / `backtest_bet` — fizycznie oddzielone od rekomendacji live.
- `provider_status` (ostatnie wywołanie, błędy, zużycie limitu).

## 4. Źródła danych (od ETAPU 4)

| Dane | Źródło | Uwagi |
|---|---|---|
| Terminarze i wyniki: PL, La Liga, Bundesliga, Liga Mistrzów | football-data.org v4 | Free: bieżący sezon, 10 zapytań/min, wyniki z opóźnieniem. |
| Historia wyników do modelu (PL, La Liga, Bundesliga, Ekstraklasa) | football-data.co.uk CSV | Bez klucza; zawiera kursy zamknięcia Pinnacle (backtest w ETAPIE 5). |
| NBA: mecze i wyniki | balldontlie | Free: 5 zapytań/min; pełny sezon raz, potem okno dat. |
| Terminarz i wyniki: Liga Europy, Ekstraklasa, Euroliga | The Odds API `/events` (0 kredytów) i `/scores` (2 kredyty) | Wyniki pobierane tylko, gdy mecz na nie czeka. |
| Składy, kontuzje | brak darmowego źródła | API-Football Free nie obsługuje bieżących sezonów (tylko 2022–2024). |
| Piłka: xG | Sportmonks (płatne dodatki) lub inne licencjonowane źródło | Bez legalnego źródła xG rynek działa na bramkach, a aplikacja to pokazuje. |
| Kursy (wiele bukmacherów) | The Odds API | Model kredytowy; trzeba sprawdzić, którzy bukmacherzy z PL są w pokryciu. |
| STS, Fortuna, Superbet, Betclic | **Brak potwierdzonych publicznych API** | Integracja tylko przez legalne źródło (agregator z licencją). Scraping z naruszeniem regulaminu — wykluczony. Do czasu weryfikacji: UI pokazuje „niedostępne”. |

Klucze API: wyłącznie w GitHub Secrets (lokalnie: `pipeline/.env`, poza repozytorium). Frontend nie zna żadnego klucza.

## 5. Harmonogram aktualizacji

**Uwaga (wariant darmowy):** poniższa tabela to docelowy harmonogram dla płatnych planów danych. W wariancie 0 zł obowiązuje budżet zapytań z sekcji 1a, a harmonogram jest skalowany automatycznie do pozostałego limitu. Częstotliwość zależy od czasu do meczu i budżetu zapytań (licznik limitu per dostawca):

| Okno do startu | Kursy | Składy / kontuzje | Przeliczenie modelu |
|---|---|---|---|
| > 72 h | co 6 h | co 12 h | po zmianie danych |
| 24–72 h | co 60 min | co 6 h | po zmianie danych |
| 2–24 h | co 15 min | co 60 min | po zmianie danych |
| < 2 h | co 5 min | co 10 min (składy potwierdzone ~60 min przed) | **obowiązkowy recheck** przed startem |

Świeżość: każda wartość ma `fetched_at`. Progi: `świeże` / `starzejące się` / `nieaktualne` zależne od typu danych i okna czasowego. Rekomendacja z nieaktualnym kursem jest oznaczana i nie trafia do TOP. Jeżeli po przeliczeniu EV ≤ 0 lub ocena < 60 → status `wycofana` z powodem (np. „kurs spadł z 2.10 do 1.85”, „potwierdzono brak kluczowego zawodnika”).

## 6. Silnik analityczny

**Piłka nożna**
- Dixon–Coles (Poisson z korektą niskich wyników) z wagą czasową, siły ataku/obrony per drużyna, przewaga gospodarza per liga; wejście: bramki + xG (jeśli dostępne, mieszanka z wagą dobraną w backteście).
- Z jednej macierzy wyników liczone są spójnie: 1X2, DC, DNB, O/U, BTTS, handicap azjatycki (z obsługą ćwiartek i zwrotów), bramki drużyn.
- Korekty: kontuzje/zawieszenia (wpływ zawodnika z minut i udziału w xG/xGA), rotacja przy napiętym terminarzu, motywacja tylko jako flaga ryzyka (nie „magiczny” mnożnik).
- Rożne / kartki: model ujemnie dwumianowy wyłącznie gdy źródło dostarcza wiarygodnych danych; inaczej rynek wyłączony z komunikatem.

**Koszykówka**
- Ratingi ofensywne/defensywne skorygowane o tempo i siłę rywali + Elo jako baseline; oczekiwana różnica punktów i suma → rozkład normalny z odchyleniem kalibrowanym per liga.
- Korekty: dostępność zawodników (wpływ ważony minutami), back-to-back, dni odpoczynku, podróż.
- Rynki: moneyline, handicap, O/U, punkty drużyn; statystyki zawodników tylko przy wiarygodnych danych.

**Wspólne**
- Rynek jako punkt odniesienia: kursy bez marży (normalizacja proporcjonalna; metoda Shina do porównania) — model musi wykazać przewagę nad rynkiem w backteście, zanim jego sygnały będą publikowane.
- Niepewność: bootstrap parametrów → przedział [p_low, p_high]; szeroki przedział obniża ocenę i podnosi ryzyko.
- Kalibracja: izotoniczna / Platt na danych poza próbą; metryki: log-loss, Brier, RPS (piłka), krzywa kalibracji.
- Backtesting walk-forward: cechy liczone wyłącznie z danych dostępnych przed `features_as_of`; kursy z migawki sprzed meczu (nie kurs zamknięcia) — ochrona przed data leakage.

**Wzory**
- p_implikowane = 1 / kurs; marża = Σ(1/kurs_i) − 1; p_fair_i = (1/kurs_i) / Σ(1/kurs_j)
- EV (na 1 jednostkę) = p_model × kurs − 1
- Edge = p_model − p_fair

**Ocena jakości sygnału (0–100)** — osobno od prawdopodobieństwa, ryzyka i EV:
składowe: wielkość przewagi względem niepewności (edge / szerokość przedziału), kompletność i świeżość danych, historyczna kalibracja modelu na danym rynku/lidze, zgodność z ruchem kursu, płynność rynku. Progi: 90+ bardzo mocny, 80–89 mocny, 70–79 interesujący, 60–69 podwyższone ryzyko, < 60 brak rekomendacji.

**Reguły twarde:** EV ≤ 0 → nigdy nie rekomenduj. Brak danych nie jest sygnałem pozytywnym — obniża ocenę. Brak wartościowych rynków → komunikat „Brak zakładów spełniających obecnie kryteria jakości…”.

## 7. Kupony (ETAP 6)

Prawdopodobieństwo kuponu liczone jako iloczyn tylko dla zdarzeń niezależnych (różne mecze, brak wspólnych czynników). Rynki z tego samego meczu są blokowane (korelacja). UI nie sugeruje, że akumulator jest bezpieczniejszy — pokazuje, że łączna marża rośnie z każdym zdarzeniem.

## 8. Bezpieczeństwo

Klucze tylko w GitHub Secrets. Walidacja schematów odpowiedzi API przed zapisem. Zapytania SQLite parametryzowane. APK podpisany stałym kluczem z GitHub Secrets. Aplikacja tylko odczytuje publiczne JSON — nie przechowuje żadnych kluczy. Historia w repozytorium = automatyczna kopia zapasowa z wersjonowaniem.

## 9. Ograniczenia środowiska budowy (stan na ETAP 1)

- Sandbox nie ma dostępu do rejestru npm/PyPI — frontend zbudowany z pakietów dostępnych lokalnie (React 19, Tailwind 4, esbuild, react-icons). `package.json` zawiera pełną listę zależności do instalacji na docelowej maszynie.
- Brak typów `@types/react` w sandboxie → pełne `tsc --noEmit` do uruchomienia po `npm install`.
- Testy na fizycznym urządzeniu z Androidem: niewykonalne z sandboxa; zastąpione emulacją mobilną Chrome (Playwright). Prawdziwy test instalacji PWA wymaga Twojego telefonu.
