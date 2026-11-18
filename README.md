# Przewaga

Osobisty asystent analityczny do zakładów: piłka nożna i koszykówka. Aplikacja na Androida (APK, Capacitor + React + TypeScript + Tailwind) oraz analiza w Pythonie uruchamiana za darmo w GitHub Actions.

**Uruchomienie: zobacz [INSTRUKCJA.md](INSTRUKCJA.md).**

**Stan: ETAPY 1–3 ukończone, aplikacja APK gotowa do budowy.** Raporty: `docs/STAGE-1-REPORT.md`, `docs/STAGE-3-REPORT.md`, architektura: `docs/ARCHITECTURE.md`.

## Uruchomienie frontendu

Wymagany jest Node.js 20+.

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (z --host także w sieci lokalnej, np. z telefonu)
npm run build      # typecheck + build produkcyjny do dist/
npm run preview
npm test           # testy jednostkowe matematyki kursów
```

Testy E2E (Playwright, emulacja Chrome na Androidzie):

```bash
npx playwright install chromium
npm run build && npx vite preview --port 4173 &
BASE_URL=http://localhost:4173 node tests/e2e/func.cjs     # testy funkcjonalne
BASE_URL=http://localhost:4173 node tests/e2e/shoot.cjs    # zrzuty 360/390/412 px + kontrola przepełnienia
```

`scripts/build-offline.mjs` to alternatywny build (esbuild + Tailwind compile API). Służy w środowisku bez dostępu do npm i daje ten sam wynik w `dist/`.

## Struktura

```
frontend/src/
  types/domain.ts      kontrakt danych (odbicie przyszłych schematów API)
  api/                 DataProvider → DemoProvider (teraz) / HttpProvider (ETAP 3)
  demo/                generator danych DEMO (wyraźnie oznaczonych)
  lib/odds.ts          implikowane p, marża, kursy bez marży, EV, Kelly, CLV (+ testy)
  components/          design system: ui/, charts/, layout/, match/
  pages/               Start, Typy, Mecze (+kalendarz), Analiza meczu, Statystyki/Historia, Profil
```

## Zasady

- Brak danych nie jest sygnałem pozytywnym. Obniża ocenę i jest wyraźnie komunikowany.
- Nigdy nie rekomendujemy zakładu z EV ≤ 0.
- Ocena analizy ≠ prawdopodobieństwo wygranej ≠ ryzyko ≠ EV. Każda z tych wartości jest pokazywana osobno.
- Klucze API wyłącznie w GitHub Secrets.

## Analiza (pipeline)

```bash
cd pipeline
pip install -r requirements.txt
python -m pytest                      # testy offline (symulowane API)
FOOTBALL_DATA_KEY=... BALLDONTLIE_KEY=... ODDS_API_KEY=... python -m app.cli run --kind morning
python -m app.cli status              # pozostałe limity zapytań
```
