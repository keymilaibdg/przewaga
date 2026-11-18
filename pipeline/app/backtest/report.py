"""docs/BACKTEST.md: the backtest report in Polish (generated, do not edit by hand)."""
from __future__ import annotations

from typing import Any

from ..config import LEAGUE_BY_KEY
from .evaluate import MAX_DIS_GRID, MIN_EV_GRID, MIN_HOLDOUT_BETS, MIN_P_BETTER, MIN_WEIGHT

MARKET = {"h2h": "1X2 / zwycięzca", "totals": "suma (O/U)", "spreads": "handicap"}
STATUS = {"validated": "✅ zweryfikowany — typy włączone", "validating": "⏳ w walidacji — typy wyłączone", "market_only": "— tylko kursy rynku"}


def pct(x: Any, d: int = 1, sign: bool = True) -> str:
    if x is None:
        return "—"
    s = f"{100 * x:+.{d}f}%" if sign else f"{100 * x:.{d}f}%"
    return s.replace(".", ",")


def num(x: Any, d: int = 4) -> str:
    return "—" if x is None else f"{x:.{d}f}".replace(".", ",")


def name(key: str) -> str:
    lg = LEAGUE_BY_KEY.get(key)
    return lg.name if lg else key


def markdown(res: dict, calib: dict) -> str:
    L: list[str] = []
    a = L.append
    a("# Backtest walk-forward i kalibracja (ETAP 5)")
    a("")
    a(f"Wygenerowano automatycznie: {res['generated_at']} (`python -m app.backtest run`, workflow „Backtest i kalibracja”). Nie edytować ręcznie.")
    a("")
    a("## Werdykt")
    a("")
    a("| Rozgrywki | Status | Uzasadnienie |")
    a("|---|---|---|")
    for key, d in calib["leagues"].items():
        a(f"| {name(key)} | {STATUS.get(d['status'], d['status'])} | {d.get('reason', '')} |")
    a("")
    a("## Metoda")
    a("")
    a("- **Walk-forward, bez wycieku danych.** Model piłkarski (Dixon–Coles) jest dopasowywany co tydzień (poniedziałek rano), tylko na meczach rozegranych wcześniej (okno 2 lata), i prognozuje mecze kolejnych 7 dni. NBA: codziennie przed meczami, okno ~1,5 sezonu.")
    a("- **Rynek jako punkt odniesienia.** Prawdopodobieństwo rynku = kursy referencyjne bez marży: Pinnacle przed meczem; gdy Pinnacle znika z plików (od 2025) — Betfair Exchange; w ostateczności średnia rynku. Ekstraklasa ma w pliku tylko kursy zamknięcia (najmocniejszy rynek → test ostrożny). NBA: konsensus zamknięcia (sportsbookreviewsonline), handicap i suma przy kursie 1,909.")
    a("- **Okres strojenia i okres testowy.** Piłka: strojenie do 30.06.2025, test od 1.07.2025 (sezon 2025/26 i bieżący). NBA: strojenie 2019/20–2021/22, test 2022/23. Na okresie testowym niczego się nie dobiera.")
    a("- **Dobór na okresie strojenia:** zanik czasowy modelu (XI) — minimalny log-loss surowego modelu; waga model/rynek — minimalny log-loss mieszanki (siatka co 0,05); skala niepewności — średnia rozbieżność model–rynek ≈ 1 półszerokość przedziału; progi "
      f"min. EV {', '.join(pct(x, 0, False) for x in MIN_EV_GRID)} i maks. rozbieżności {', '.join(pct(x, 0, False) for x in MAX_DIS_GRID)} — maksimum (ROI − 1 błąd standardowy), min. 60 typów.")
    a("- **Symulacja zakładów = ten sam kod co na żywo** (`engine.evaluate.price_market`): ta sama ocena jakości, progi, limit kursu 5,0, maks. 2 typy na mecz. Kurs wzięty = najlepszy kurs rynku (maksimum z plików, wartości odstające >25% ponad średnią zastąpione średnią). Wyniki pokazane też przy kursach średnich i po podatku 12%.")
    a(f"- **Reguła walidacji (ustalona przed obejrzeniem wyników):** rynek ligi dostaje typy tylko, jeśli waga modelu ≥ {MIN_WEIGHT:.2f}, na okresie testowym mieszanka ma niższy log-loss niż sam rynek z prawdopodobieństwem bootstrap ≥ {MIN_P_BETTER:.2f}, było ≥ {MIN_HOLDOUT_BETS} typów i ROI ≥ 0. W przeciwnym razie model jest pokazywany, ale typy są wyłączone (status „w walidacji”).")
    a("")
    fb = res.get("football", {})
    a("## Piłka nożna")
    a("")
    a(f"Zanik czasowy (log-loss 1X2 na okresie strojenia): {', '.join(f'XI={k}: {num(v, 5)}' for k, v in (fb.get('xi_grid') or {}).items())} → wybrano **XI={fb.get('xi')}**.")
    a("")
    for lg, d in (fb.get("leagues") or {}).items():
        a(f"### {name(lg)}")
        a("")
        a(f"Sezony: {', '.join(d['seasons'])}. Wiersze (rynek × mecz): strojenie {d['rows_tune']}, test {d['rows_hold']}. Źródła kursu referencyjnego: {', '.join(d['ref_sources'])}. "
          f"Progi: min. EV {pct(d['min_ev'], 0, False)}, maks. rozbieżność model–rynek {pct(d['max_disagreement'], 0, False)}.")
        a("")
        a(_market_table(d["markets"]))
        a(_sim_line("Strojenie", d["sim_tune"]))
        a(_sim_line("Test", d["sim_hold"]))
        a("")
    nba = res.get("nba", {})
    a("## NBA")
    a("")
    if nba.get("error"):
        a(f"Brak: {nba['error']}. {'; '.join(nba.get('skipped', []))}")
    else:
        a(f"Mecze z kursami: {nba.get('games')}. Zanik: {', '.join(f'XI={k}: {num(v, 5)}' for k, v in (nba.get('xi_grid') or {}).items())} → **XI={nba.get('xi')}**. Uwaga: {nba.get('price_note')}.")
        a("")
        a(_market_table(nba["markets"]))
        a(_sim_line("Strojenie", nba["sim_tune"]))
        a(_sim_line("Test", nba["sim_hold"]))
        fat = nba.get("fatigue")
        if fat:
            c = fat.get("coefficients") or {}
            a("")
            a(f"Zmęczenie i terminarz (dni odpoczynku, back-to-back, podróż): **{'używane w modelu' if fat['used'] else 'nie poprawiły modelu — wyłączone'}**. "
              f"Log-loss surowego modelu na strojeniu bez / z: 1X2 {num(fat['tune_logloss']['bez'].get('h2h'), 5)} / {num(fat['tune_logloss']['z'].get('h2h'), 5)}, "
              f"handicap {num(fat['tune_logloss']['bez'].get('spreads'), 5)} / {num(fat['tune_logloss']['z'].get('spreads'), 5)}. "
              f"Efekty (punkty różnicy dla gospodarza): dzień odpoczynku więcej {num(c.get('rest_diff'), 2)}, gospodarz b2b {num(c.get('b2b_home'), 2)}, gość b2b {num(c.get('b2b_away'), 2)}, "
              f"1000 km podróży gościa więcej {num(c.get('travel_1000km'), 2)}.")
        sc = nba.get("sigma_check")
        if sc:
            a("")
            a(f"Kontrola rozkładu (test): w ±1σ różnicy punktów {pct(sc['margin_within_1sigma'], 0, False)}, sumy {pct(sc['total_within_1sigma'], 0, False)} (oczekiwane ~68%); "
              f"odch. std z-score: różnica {num(sc['margin_z_sd'], 2)}, suma {num(sc['total_z_sd'], 2)}; średni błąd sumy {num(sc['total_bias'], 1)} pkt.")
    a("")
    cups = res.get("cups", {})
    a("## Puchary (Liga Mistrzów, Liga Europy): ratingi międzyligowe")
    a("")
    if cups.get("error"):
        a(f"Brak: {cups['error']}.")
    else:
        a(f"Model łączny: {cups.get('domestic_matches')} meczów ligowych z 21 lig krajowych (football-data.co.uk) + {cups.get('cup_matches')} meczów pucharowych (API-Football 2022–2024 i bieżący sezon z bazy), {cups.get('teams')} drużyn.")
        v = cups.get("validation")
        if v:
            a("")
            a(f"Test: {v['season']}, {v['matches']} meczów z drużynami o wystarczającej historii. Log-loss 1X2: model **{num(v['logloss_model'])}**, punkt odniesienia ({v['baseline']}) {num(v['logloss_baseline'])}.")
            if v.get("calibration"):
                a("")
                a("| Prognoza (średnio) | Wynik (częstość) | Liczba |")
                a("|---|---|---|")
                for b in v["calibration"]:
                    a(f"| {pct(b['predicted'], 0, False)} | {pct(b['observed'], 0, False)} | {b['count']} |")
        a("")
        a("Darmowe źródła nie mają historii kursów pucharowych, więc przewagi nad rynkiem nie da się jeszcze sprawdzić: model jest pokazywany w aplikacji, typy pozostają wyłączone, a kursy zbierane codziennie posłużą do walidacji.")
    a("")
    a("## Tryb rynkowy (bez modelu)")
    a("")
    a("Typ = najlepszy kurs rynku co najmniej 3% powyżej kursu uczciwego (kurs referencyjny po odjęciu marży), kurs ≤ 4,0, najwyżej 15% ponad kurs średni, "
      "linie połówkowe. Reguły ustalone z góry (nic nie dobierano na danych), więc liczą się wszystkie sezony. Kluczowa miara: EV wobec linii zamknięcia "
      "(czy kurs wzięty był lepszy od uczciwego kursu tuż przed meczem) — mniej zależna od szczęścia niż ROI.")
    a("")
    a("| Liga | Typy | Trafność | Śr. kurs | ROI (kurs najlepszy) | ROI po podatku | EV wobec zamknięcia | Test od 1.07.2025: typy / ROI |")
    a("|---|---|---|---|---|---|---|---|")
    for lg, d in (fb.get("leagues") or {}).items():
        mm = d.get("market_mode") or {}
        s_, h_ = mm.get("all") or {}, mm.get("hold") or {}
        if not s_.get("bets"):
            a(f"| {name(lg)} | 0 | — | — | — | — | — | — |")
            continue
        a(f"| {name(lg)} | {s_['bets']} | {pct(s_['hit_rate'], 1, False)} | {num(s_['avg_price'], 2)} | {pct(s_['roi'])} (±{pct(s_['roi_se'], 1, False)}) | {pct(s_['roi_taxed'])} | "
          f"{pct(s_['ev_close'])} | {h_.get('bets', 0)} / {pct(h_.get('roi'))} |")
    a("")
    a("NBA: archiwum ma jeden kurs na mecz (konsensus), więc trybu rynkowego nie da się sprawdzić na historii — w aplikacji działa na bieżących kursach wielu bukmacherów.")
    a("")
    a("## Niskie kursy: czy to pułapka?")
    a("")
    a("Wszystkie mecze z kursami (bez modelu). Kurs średni rynku przed meczem; „wygrane” = jak często selekcja w tym przedziale kursu faktycznie wygrała; "
      "zwrot = wynik obstawiania każdej takiej selekcji po 1 zł.")
    a("")
    pb = dict(res.get("football", {}).get("price_buckets") or {})
    if res.get("nba", {}).get("price_buckets"):
        pb["nba"] = res["nba"]["price_buckets"]
    for lg, d in pb.items():
        rows = [b for b in d["buckets"] if b["to"] <= 1.8]
        if not rows:
            continue
        a(f"**{name(lg)}** ({d['matches']} meczów, {d['source']}):")
        a("")
        a("| Kurs | Liczba | Wygrane (95% przedział) | Zakładał kurs | bez marży | Zwrot przy kursie średnim | przy najlepszym | po podatku 12% |")
        a("|---|---|---|---|---|---|---|---|")
        for b in rows:
            a(f"| {num(b['from'], 2)}–{num(b['to'], 2)} | {b['n']} | {pct(b['winRate'], 1, False)} ({pct(b['winRateLow'], 0, False)}–{pct(b['winRateHigh'], 0, False)}) | "
              f"{pct(b['implied'], 1, False)} | {pct(b['fair'], 1, False)} | {pct(b['roiAvg'])} | {pct(b['roiBest'])} | {pct(b['roiTaxed'])} |")
        a("")
    a("## Ograniczenia")
    a("")
    a("- Kurs „najlepszy rynku” z plików to maksimum z kilkudziesięciu bukmacherów — w praktyce trudniej osiągalny niż średnia; dlatego raport podaje też ROI przy kursach średnich i po podatku 12%.")
    a("- NBA: archiwum kursów kończy się na sezonie 2022/23; spread i suma bez kursów (przyjęto 1,909).")
    a("- Brak danych o kontuzjach i składach w darmowych źródłach — model ich nie widzi, co ogranicza jego przewagę nad rynkiem.")
    a("- Mała próba = duża wariancja: ROI z kilkudziesięciu typów nie dowodzi przewagi. Decyduje przede wszystkim log-loss (właściwa reguła oceny) na okresie testowym.")
    a("")
    return "\n".join(L)


def _market_table(markets: dict) -> str:
    rows = [
        "| Rynek | Waga modelu | Skala niepewności | Log-loss: model / rynek / mieszanka (test) | Δ vs rynek (test) | P(lepszy) | Typy (test) | ROI (test) | Status |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m, r in markets.items():
        h, b, s = r.get("hold") or {}, r.get("boot") or {}, r.get("sim_hold") or {}
        rows.append(
            f"| {MARKET.get(m, m)} | {num(r['weight'], 2)} | {num(r['hw_scale'], 2)} | {num(h.get('logloss_model'))} / {num(h.get('logloss_market'))} / {num(h.get('logloss_blend'))} | "
            f"{num(b.get('delta'), 5)} | {num(b.get('p_better'), 2)} | {s.get('bets', 0)} | {pct(s.get('roi'))} | {STATUS.get(r['status'], r['status']).split(' — ')[0]} {r['reason']} |"
        )
    return "\n".join(rows) + "\n"


def _sim_line(label: str, s: dict) -> str:
    if not s or not s.get("bets"):
        return f"- {label}: brak typów."
    return (
        f"- {label}: {s['bets']} typów, trafność {pct(s['hit_rate'], 1, False)}, średni kurs {num(s['avg_price'], 2)}, ROI {pct(s['roi'])} (±{pct(s['roi_se'], 1, False)}), "
        f"przy kursach średnich {pct(s['roi_avg_odds'])}, po podatku 12% {pct(s['roi_taxed'])}, CLV {pct(s['clv'])}, EV wobec linii zamknięcia {pct(s['ev_close'])}."
    )
