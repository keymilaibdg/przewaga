import { useState } from "react";
import { LuCheck, LuChevronRight, LuPlus, LuReceiptText } from "react-icons/lu";
import { useCoupon } from "../../api/CouponContext";
import { bookmakerName } from "../../lib/bookmakers";
import { cn } from "../../lib/cn";
import { fmtKickoff, fmtPct, fmtPrice, fmtSignedPct } from "../../lib/format";
import type { AppPick } from "../../lib/picks";
import { navigate } from "../../router";
import { Card } from "../ui/primitives";
import { MarketBadge } from "./MarketBadge";
import { SportIcon } from "./SportIcon";

export const PICKS_NOTE =
  "Typ aplikacji to najbardziej prawdopodobny wynik według rynku (kursy bez marży). Taki typ nie ma przewagi nad bukmacherem — po podatku średnio tracisz tyle, ile pokazuje „EV po podatku”. Wyjątek: typy oznaczone jako okazja (zielona ramka).";

export function PickRow({ p }: { p: AppPick }) {
  const coupon = useCoupon();
  const [note, setNote] = useState<string | null>(null);
  const on = coupon.has(p.selection.id);
  return (
    <div className={cn("rounded-xl p-3 ring-1 ring-inset", p.value ? "bg-pos/[0.06] ring-pos/25" : "bg-ink-800/60 ring-line")}>
      <div className="flex items-center gap-2 text-[11px] text-fg-faint">
        <SportIcon sport={p.event.sport} className="size-3.5" />
        <span className="truncate">{p.event.league.name}</span>
        <span className="tnum ml-auto shrink-0">{fmtKickoff(p.event.kickoff)}</span>
      </div>
      <div className="mt-1.5 flex items-center gap-3">
        <button type="button" className="min-w-0 flex-1 text-left" onClick={() => navigate(`/mecz/${encodeURIComponent(p.event.id)}`)}>
          <div className="truncate text-[12px] text-fg-muted">
            {p.event.home.name} – {p.event.away.name}
          </div>
          <div className="flex items-center gap-1 truncate text-[15px] font-semibold">
            {p.selection.label} <LuChevronRight className="size-3.5 shrink-0 text-fg-faint" />
          </div>
        </button>
        <div className="text-right">
          <div className="tnum text-lg font-bold">{fmtPrice(p.price)}</div>
          <div className="text-[10px] text-fg-faint">{bookmakerName(p.bookmaker)}</div>
        </div>
        <button
          type="button"
          onClick={() => setNote(coupon.toggle(p.event, p.selection))}
          className={cn("grid size-9 shrink-0 place-items-center rounded-full ring-1 ring-inset", on ? "bg-accent text-ink-950 ring-accent" : "text-fg-muted ring-line-strong hover:bg-white/5")}
          aria-label={on ? `Usuń z kuponu: ${p.selection.label}` : `Dodaj do kuponu: ${p.selection.label}`}
          aria-pressed={on}
        >
          {on ? <LuCheck className="size-4" /> : <LuPlus className="size-4" />}
        </button>
      </div>
      <div className="tnum mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-fg-faint">
        <span>
          Szansa <b className="text-fg-muted">{fmtPct(p.prob)}</b>
        </span>
        <span className={p.evTaxed >= 0 ? "text-pos" : "text-neg"}>EV po podatku {fmtSignedPct(p.evTaxed)}</span>
        {p.value?.kind === "market" ? <MarketBadge /> : p.value ? <span className="font-semibold text-pos">Typ modelu</span> : null}
      </div>
      {note && <p className="mt-2 text-[11px] text-warn">{note}</p>}
    </div>
  );
}

/** List of picks with a one-tap "add the N most likely to the coupon". */
export function AppPicksCard({ picks, title, subtitle, quick = 3 }: { picks: AppPick[]; title: string; subtitle?: string; quick?: number }) {
  const coupon = useCoupon();
  const [msg, setMsg] = useState<string | null>(null);
  if (picks.length === 0) return null;
  const addTop = () => {
    const added = coupon.addMany(picks.slice(0, quick).map((p) => ({ event: p.event, sel: p.selection })));
    setMsg(added ? `Dodano ${added} do kuponu.` : "Te typy są już w kuponie.");
    if (added) coupon.setOpen(true);
  };
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      {subtitle && <p className="mt-0.5 text-xs text-fg-faint">{subtitle}</p>}
      <div className="mt-3 space-y-2">
        {picks.map((p) => (
          <PickRow key={p.selection.id} p={p} />
        ))}
      </div>
      {picks.length >= 2 && (
        <button type="button" onClick={addTop} className="mt-3 flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-accent text-sm font-semibold text-ink-950 active:scale-[0.98]">
          <LuReceiptText className="size-4" /> Dodaj {Math.min(quick, picks.length)} najpewniejsze do kuponu
        </button>
      )}
      {msg && <p className="mt-2 text-center text-[11px] text-fg-faint">{msg}</p>}
      <p className="mt-3 text-[11px] leading-relaxed text-fg-faint">{PICKS_NOTE}</p>
    </Card>
  );
}
