# Przewaga: uruchomienie krok po kroku (0 zł)

Czas: ok. 20–30 minut. Wszystko robisz raz. Potem aplikacja sama aktualizuje analizy 1–2 razy dziennie.

## Czego potrzebujesz
- Konto GitHub (darmowe): przechowuje kod, codziennie uruchamia analizę i buduje plik APK.
- Klucz API-Football (darmowy, bez karty): terminarze, wyniki, kontuzje.
- Klucz The Odds API (darmowy, bez karty): kursy bukmacherów.
- Plik `przewaga-podpis.txt`, który dostałeś ode mnie: klucz podpisu aplikacji. **Nie publikuj go nigdzie.**

---

## Krok 1. Konto i repozytorium GitHub
1. Wejdź na **github.com** i załóż konto („Sign up”).
2. Po zalogowaniu kliknij **+** (prawy górny róg) → **New repository**.
3. Repository name: `przewaga`. Zaznacz **Public**. Nie zaznaczaj „Add a README”.
4. Kliknij **Create repository**.
5. Napisz mi nazwę swojego konta GitHub. Wgram cały kod do repozytorium (poproszę o potwierdzenie dostępu).

## Krok 2. Klucze football-data.org i balldontlie
1. **football-data.org**: wejdź na **football-data.org/client/register**, zarejestruj się (plan Free). Klucz przyjdzie mailem.
2. **balldontlie**: wejdź na **app.balldontlie.io**, zarejestruj się (plan Free). Klucz jest w panelu (Account → API Key).
3. Historia wyników z **football-data.co.uk** nie wymaga klucza.

## Krok 3. Klucz The Odds API
1. Wejdź na **the-odds-api.com** i w sekcji planów wybierz **Starter (FREE)** → **START**.
2. Podaj e-mail. Klucz przyjdzie mailem.

## Krok 4. Sekrety w repozytorium
W repozytorium: **Settings → Secrets and variables → Actions → New repository secret**. Dodaj sekrety (nazwa musi być dokładnie taka):

| Nazwa | Wartość |
|---|---|
| `FOOTBALL_DATA_KEY` | klucz football-data.org z kroku 2 |
| `BALLDONTLIE_KEY` | klucz balldontlie z kroku 2 |
| `ODDS_API_KEY` | klucz z kroku 3 |
| `ANDROID_KEYSTORE_PASSWORD` | 24-znakowe hasło z pliku `przewaga-podpis.txt` |

Klucz podpisu leży w repozytorium w postaci zaszyfrowanej (`frontend/signing/`). Bez hasła jest bezużyteczny, dlatego hasło trzymaj tylko w sekretach.

Sekrety są szyfrowane: nikt ich nie zobaczy, także w publicznym repozytorium.

## Krok 5. Pierwsze uruchomienie
1. Zakładka **Actions**. Jeśli GitHub zapyta, kliknij „I understand my workflows, go ahead and enable them”.
2. Po lewej wybierz **Aktualizacja danych** → **Run workflow** → **Run workflow**. Pierwsze uruchomienie trwa ok. 8 minut (pobiera dwa sezony NBA z limitem 5 zapytań na minutę), kolejne 1–3 minuty. Zielony znaczek oznacza sukces.
3. Po lewej wybierz **Budowa aplikacji Android (APK)** → **Run workflow**. Trwa ok. 10 minut.

## Krok 6. Instalacja na telefonie
1. W repozytorium kliknij **Releases** (po prawej stronie) albo otwórz `github.com/TWOJA-NAZWA/przewaga/releases/latest`.
2. Stuknij plik **Przewaga-….apk** i pobierz go.
3. Otwórz pobrany plik. Android zapyta o zgodę na instalację z tego źródła: zezwól.
4. Jeśli pojawi się ostrzeżenie Play Protect („nieznana aplikacja”), wybierz **Zainstaluj mimo to**. Plik nie pochodzi ze Sklepu Play, dlatego jest ostrzeżenie.

## Krok 7. Wysłanie znajomemu
Wyślij mu link `github.com/TWOJA-NAZWA/przewaga/releases/latest` (np. Messengerem). On robi tylko krok 6 i nie potrzebuje żadnych kont ani kluczy.

---

## Jak to działa na co dzień
- **07:17** (i opcjonalnie **15:47**, jeśli pozwala limit kursów) GitHub sam pobiera dane, liczy modele i publikuje analizy. Aplikacja pobiera je przy otwarciu.
- Bez internetu aplikacja pokazuje ostatnie pobrane dane z oznaczeniem „Offline”.
- **Backtest i kalibracja** (workflow „Backtest i kalibracja”): 1. dnia miesiąca GitHub sam sprawdza model na historii i ustala, w których ligach wolno mu dawać typy; w poniedziałki odświeża ratingi drużyn pucharowych. Wynik: **Statystyki → Backtest** w aplikacji i plik `docs/BACKTEST.md`. Nic nie trzeba klikać.
- **Powiadomienia (od v0.5):** w **Profilu → Powiadomienia** naciśnij „Zezwól na powiadomienia”. Telefon sam sprawdza nowe analizy mniej więcej co 2 godziny i przypomina godzinę przed meczami z kuponu. Jeśli powiadomienia nie przychodzą, wyłącz dla aplikacji Przewaga optymalizację baterii (Ustawienia → Aplikacje → Przewaga → Bateria → Bez ograniczeń).
- **Okazje rynkowe (od v0.6):** gdy model nie ma typu, aplikacja pokazuje „okazje rynkowe” — kurs u któregoś bukmachera wyższy od uczciwego kursu rynku. To nie prognoza, tylko porównanie kursów; przy każdej jest minimalny kurs, jaki musi dać legalny polski bukmacher (po podatku). Wyłączysz je w **Profilu → Okazje rynkowe**.
- **Kontuzje NBA:** w meczach NBA widać nieobecnych z oficjalnego raportu ligi (aktualizacja przy każdym przebiegu).
- **Kupon:** w analizie meczu, w zakładce **Rynki**, przycisk **+** dodaje selekcję do kuponu (jedna na mecz). Kupon otwiera się przyciskiem nad dolnym menu.
- Nowa wersja aplikacji: w **Profilu** pojawi się „Pobierz aktualizację”. Instaluje się na poprzednią wersję i zachowuje ustawienia.

## Gdy coś nie działa
- **Profil → Źródła danych:** pokazuje, które źródło działa, a które zwróciło błąd.
- **GitHub → Actions:** czerwony znaczek przy przebiegu = błąd. Kliknij go i prześlij mi treść, naprawię.
- **„Brak danych do wyświetlenia” w aplikacji:** pierwsza aktualizacja (krok 5.2) jeszcze się nie wykonała albo telefon nie ma internetu.

## Ważne
- Darmowe plany mają limity: 100 zapytań dziennie (API-Football) i 500 kredytów miesięcznie (kursy). Dlatego analizy aktualizują się 1–2 razy dziennie, a nie co kilka minut.
- Kursy w aplikacji pochodzą od bukmacherów europejskich i służą jako punkt odniesienia. **W Polsce obstawiaj tylko u bukmacherów z zezwoleniem Ministra Finansów.** Przy każdym typie aplikacja podaje minimalny kurs, który musi dać Twój bukmacher, żeby zakład miał sens po potrąceniu 12% podatku od stawki.
- 18+. Aplikacja jest narzędziem analitycznym i nie gwarantuje wygranej.
