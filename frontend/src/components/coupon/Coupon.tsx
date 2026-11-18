import { useMemo, useState } from "react";
import { LuBellRing, LuReceiptText, LuTrash2, LuTriangleAlert, LuX } from "react-icons/lu";
import { useCoupon } from "../../api/CouponContext";
import { useData } from "../../api/DataContext";
import { summarize } from "../../lib/coupon";
import { bookmakerName } from "../../lib/bookmakers";
import { cn } from "../../lib/cn";
import { fmtKickoff, fmtPct, fmtPrice, fmtSignedPct } from "../../lib/format";
import { navigate } from "../../router";
import { Sheet } from "../ui/Sheet";
import { Slider } from "../ui/Slider";

/** Floating coupon button above the bottom navigation (visible when the coupon is not empty). */
export function CouponButton() {
  const c = useCoupon();
  if (c.legs.length === 0) return null;
  const odds = c.legs.reduce((s, l) => s * l.leg.price, 1);
  return (
    <>
      <button
        type="button"
        onClick={() => c.setOpen(true)}
        className="animate-fade-up fixed right-4 bottom-[calc(4.75rem+env(safe-area-inset-bottom))] z-40 flex h-12 items-center gap-2 rounded-full bg-accent pr-4 pl-3 font-semibold text-ink-950 shadow-lg shadow-black/40 active:scale-[0.97]"
        aria-label={`Kupon: ${c.legs.length} zdarzeń, kurs ${fmtPrice(odds)}`}
      >
        <span className="relative">
          <LuReceiptText className="size-5" />
          <span className="absolute -top-2 -right-2 grid size-4 place-items-center rounded-full bg-ink-950 text-[10px] text-accent">{c.legs.length}</span>
        </span>
        <span className="tnum text-sm">{fmtPrice(odds)}</span>
      </button>
      <Sheet open={c.open} onClose={() => c.setOpen(false)} title="Kupon">
        <CouponPanel />
      </Sheet>
    </>
  );
}

const STATE_NOTE = {
  started: "Mecz się rozpoczął — usuń z kuponu",
  missing: "Selekcja zniknęła z oferty — kurs nieaktualny",
  price_changed: "Kurs się zmienił",
  ok: "",
} as const;

export function CouponPanel() {
  const c = useCoupon();
  const { settings } = useData();
  const [units, setUnits] = useState(1);
  const legs = c.legs.map((r) => r.leg);
  const s = useMemo(() => summarize(legs, units * settings.unitStake, settings.stakeTax), [legs, units, settings.unitStake, settings.stakeTax]);
  const problems = c.legs.filter((r) => r.state === "started" || r.state === "missing").length;

  if (c.legs.length === 0) return <p className="py-6 text-center text-sm text-fg-faint">Kupon jest pusty. Dodaj selekcje z zakładki „Rynki” w analizie meczu.</p>;

  return (
    <div className="space-y-4">
      <ul className="space-y-2">
        {c.legs.map(({ leg, state, previousPrice }) => (
          <li key={leg.selectionId} className={cn("rounded-xl p-3 ring-1 ring-inset", state === "started" || state === "missing" ? "bg-neg/[0.06] ring-neg/25" : "bg-ink-800/60 ring-line")}>
            <div className="flex items-start gap-2">
              <button
                type="button"
                className="min-w-0 flex-1 text-left"
                onClick={() => {
                  c.setOpen(false);
                  navigate(`/mecz/${encodeURIComponent(leg.eventId)}`);
                }}
              >
                <div className="truncate text-[13px] font-medium">{leg.label}</div>
                <div className="truncate text-[11px] text-fg-faint">
                  {leg.eventLabel} · {leg.league} · {fmtKickoff(leg.kickoff)}
                </div>
              </button>
              <div className="text-right">
                <div className="tnum text-[15px] font-bold">{fmtPrice(leg.price)}</div>
                <div className="text-[10px] text-fg-faint">{bookmakerName(leg.bookmaker)}</div>
              </div>
              <button type="button" onClick={() => c.remove(leg.selectionId)} className="-mr-1 grid size-8 place-items-center rounded-full text-fg-faint hover:bg-white/5" aria-label={`Usuń ${leg.label}`}>
                <LuX className="size-4" />
              </button>
            </div>
            <div className="tnum mt-1.5 flex gap-3 text-[11px] text-fg-faint">
              <span>Prawdop. {fmtPct(leg.prob)}</span>
              <span>Rynek {fmtPct(leg.fairProb)}</span>
              <span className={cn("ml-auto", leg.prob * leg.price - 1 >= 0 ? "text-pos" : "text-neg")}>EV {fmtSignedPct(leg.prob * leg.price - 1)}</span>
            </div>
            {state !== "ok" && (
              <p className={cn("mt-1 text-[11px]", state === "price_changed" ? "text-warn" : "text-neg")}>
                {STATE_NOTE[state]}
                {previousPrice !== null && ` (było ${fmtPrice(previousPrice)})`}
              </p>
            )}
          </li>
        ))}
      </ul>

      <div className="grid grid-cols-2 gap-2 rounded-2xl bg-ink-800/60 p-4 ring-1 ring-line ring-inset">
        <Stat label="Kurs łączny" value={fmtPrice(s.odds)} />
        <Stat label="Szansa wygranej" value={fmtPct(s.prob)} hint={s.prob > 0 ? `ok. 1 na ${Math.max(1, Math.round(1 / s.prob))}` : undefined} />
        <Stat label="Kurs godziwy" value={Number.isFinite(s.fairOdds) ? fmtPrice(s.fairOdds) : "—"} hint="przy którym EV = 0" />
        <Stat label="EV po podatku" value={fmtSignedPct(s.evTaxed)} tone={s.evTaxed >= 0 ? "pos" : "neg"} hint={`bez podatku ${fmtSignedPct(s.ev)}`} />
        <Stat label="Marża kuponu" value={fmtPct(s.margin)} tone="neg" hint={`śr. na zdarzenie ${fmtPct(s.avgLegMargin)}`} />
        <Stat label="Wypłata przy wygranej" value={`${s.payout.toFixed(2).replace(".", ",")} zł`} hint={`stawka ${s.stake} zł, po podatku ${fmtPct(settings.stakeTax, 0)}`} />
      </div>

      <Slider label="Stawka" value={units} min={1} max={Math.max(1, settings.dailyLimitUnits)} step={1} display={`${units} j. (${units * settings.unitStake} zł)`} onChange={setUnits} />

      <div className="space-y-2 text-[11px] leading-relaxed text-fg-muted">
        {problems > 0 && (
          <p className="flex gap-2 text-neg">
            <LuTriangleAlert className="mt-0.5 size-3.5 shrink-0" /> {problems} {problems === 1 ? "zdarzenie wymaga" : "zdarzenia wymagają"} uwagi — usuń je przed obstawieniem.
          </p>
        )}
        <p className="flex gap-2">
          <LuTriangleAlert className="mt-0.5 size-3.5 shrink-0 text-warn" />
          Każde zdarzenie dokłada marżę bukmachera: kupon nie jest bezpieczniejszy od pojedynczych zakładów — szansa wygranej to iloczyn szans, a oczekiwana strata rośnie z liczbą zdarzeń.
        </p>
        <p>
          Prawdopodobieństwo liczone jako iloczyn zakłada niezależność zdarzeń, dlatego kupon przyjmuje jeden typ na mecz. Kursy pochodzą od bukmacherów europejskich — u polskiego bukmachera sprawdź kurs każdego zdarzenia. Kupon to kalkulator: nic nie jest
          wysyłane do bukmachera.
        </p>
        {settings.notifications.couponReminders && __NATIVE__ && (
          <p className="flex gap-2">
            <LuBellRing className="mt-0.5 size-3.5 shrink-0 text-accent" /> Przypomnienie godzinę przed każdym meczem z kuponu (Profil → Powiadomienia).
          </p>
        )}
      </div>

      <button type="button" onClick={c.clear} className="flex h-11 w-full items-center justify-center gap-2 rounded-xl text-sm font-medium text-fg-muted ring-1 ring-line ring-inset hover:bg-white/5">
        <LuTrash2 className="size-4" /> Wyczyść kupon
      </button>
    </div>
  );
}

function Stat({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "pos" | "neg" }) {
  return (
    <div>
      <div className="text-[11px] text-fg-faint">{label}</div>
      <div className={cn("tnum text-base font-bold", tone === "pos" && "text-pos", tone === "neg" && "text-neg")}>{value}</div>
      {hint && <div className="text-[10px] text-fg-faint">{hint}</div>}
    </div>
  );
}
