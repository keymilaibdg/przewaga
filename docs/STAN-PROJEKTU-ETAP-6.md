# ETAP 6: kupony i powiadomienia lokalne — stan projektu

Stan na 2026-11-18 (gałąź `etap-6`, aplikacja v0.5).

## Kupon
- Przycisk **+** przy każdej selekcji w analizie meczu (zakładka **Rynki**). Kupon otwiera się przyciskiem nad dolnym menu (liczba zdarzeń i kurs łączny).
- **Jeden typ na mecz:** druga selekcja z tego samego meczu zastępuje pierwszą z komunikatem (zdarzenia z jednego meczu są skorelowane, a szansa kuponu liczona jako iloczyn wymaga niezależności). Maks. 12 zdarzeń. Mecz, który się rozpoczął, nie może zostać dodany.
- Pokazuje: kurs łączny, szansę wygranej („ok. 1 na N”), kurs godziwy, EV bez podatku i po 12% podatku, **marżę kuponu** na tle średniej marży zdarzenia (rośnie z każdym zdarzeniem), wypłatę po podatku. Stawka w jednostkach z Profilu, maksymalnie do dziennego limitu.
- Po każdym pobraniu danych kursy w kuponie są aktualizowane; zdarzenie ze zmienionym kursem, rozpoczęte albo zdjęte z oferty jest oznaczone.
- Kupon jest kalkulatorem zapisanym w telefonie — nic nie trafia do bukmachera. Ostrzeżenie: kupon nie jest bezpieczniejszy od pojedynczych zakładów.
- Kod: `frontend/src/lib/coupon.ts` (+6 testów), `api/CouponContext.tsx`, `components/coupon/Coupon.tsx`.

## Powiadomienia (tylko APK)
- **Sprawdzanie w tle** (`@capacitor/background-runner` 2.3, skrypt `public/runners/background.js`): mniej więcej co 2 godziny telefon pobiera `meta.json` z gałęzi `data` i pokazuje nowe powiadomienia: nowa okazja, wycofany typ, rozliczony typ (wg przełączników w Profilu). Pierwsze sprawdzenie tylko zapamiętuje istniejące powiadomienia (bez zalewu). Maks. 4 powiadomienia naraz + zbiorcze.
- **Przypomnienia o meczach z kuponu** (`@capacitor/local-notifications` 7): godzinę przed każdym meczem z kuponu; aktualizowane przy każdej zmianie kuponu.
- **Profil → Powiadomienia:** przycisk „Zezwól na powiadomienia” (Android 13+), przełączniki: nowe okazje, wycofane, rozliczone, przypomnienia o kuponie; „zmiany kursów” i „składy” opisane jako niedostępne w darmowych danych.
- Bez serwera i bez kont: aplikacja przekazuje skryptowi w tle tylko adres danych i ustawienia.
- Ograniczenie: Android może opóźniać zadania w tle (tryb oszczędzania baterii) — instrukcja podaje, jak wyłączyć optymalizację baterii dla aplikacji.

## Build i testy
- `android.yml`: build także na gałęzi `etap-6` (APK jako artefakt, bez publikacji w Releases); do `build.gradle` dopisywana biblioteka silnika JS background-runnera (z kontrolą).
- Testy TS: 18/18 (w tym kupon). Pełny `tsc --noEmit` bez błędów (pliki testów node wyłączone z kontroli typów). Build APK na GitHubie: sukces.
- **Niewykonane:** test na fizycznym telefonie (powiadomienia w tle, zgoda Android 13+) — do sprawdzenia przez użytkownika po instalacji v0.5 (ETAP 7).

## Dalej
ETAP 7: testy na urządzeniu, raport końcowy. Otwarte decyzje: „tryb rynkowy” (progi kursów dla polskich bukmacherów), nowa ikona.
