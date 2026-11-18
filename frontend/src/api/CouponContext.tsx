// Coupon state kept on the phone (localStorage). Legs are re-priced whenever new analyses are loaded.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { addLeg, removeLeg, reprice, type CouponLeg, type PricedSelection, type RepricedLeg } from "../lib/coupon";
import { bestQuote } from "../lib/odds";
import { scheduleCouponReminders } from "../lib/notify";
import type { SelectionAnalysis, SportEvent } from "../types/domain";
import { useData } from "./DataContext";

const KEY = "przewaga.coupon.v1";

interface CouponValue {
  legs: RepricedLeg[];
  has: (selectionId: string) => boolean;
  /** Adds the selection, or removes it when already on the coupon. Returns a message for the user, if any. */
  toggle: (event: SportEvent, sel: SelectionAnalysis) => string | null;
  remove: (selectionId: string) => void;
  /** Adds several selections at once (one per match); returns how many were added. */
  addMany: (items: { event: SportEvent; sel: SelectionAnalysis }[]) => number;
  clear: () => void;
  open: boolean;
  setOpen: (v: boolean) => void;
}

const Ctx = createContext<CouponValue | null>(null);

function load(): CouponLeg[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as CouponLeg[]) : [];
  } catch {
    return [];
  }
}

function save(legs: CouponLeg[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(legs));
  } catch {
    /* storage unavailable: coupon lives in memory only */
  }
}

export function legFrom(event: SportEvent, sel: SelectionAnalysis): CouponLeg {
  const best = bestQuote(sel.quotes);
  return {
    selectionId: sel.id,
    eventId: event.id,
    eventLabel: `${event.home.shortName || event.home.name} – ${event.away.shortName || event.away.name}`,
    league: event.league.name,
    sport: event.sport,
    kickoff: event.kickoff,
    market: sel.market,
    label: sel.label,
    price: best?.price ?? 0,
    bookmaker: best?.bookmaker ?? "",
    prob: sel.modelProb,
    fairProb: sel.fairProb,
    addedAt: new Date().toISOString(),
  };
}

export function CouponProvider({ children }: { children: ReactNode }) {
  const { provider, settings, revision } = useData();
  const [legs, setLegs] = useState<CouponLeg[]>(load);
  const [latest, setLatest] = useState<Map<string, PricedSelection>>(new Map());
  const [open, setOpen] = useState(false);

  // newest prices for every selection on the coupon
  useEffect(() => {
    let alive = true;
    provider.getEvents({}).then((events) => {
      if (!alive) return;
      const m = new Map<string, PricedSelection>();
      for (const e of events)
        for (const mk of e.markets)
          for (const s of mk.selections) {
            const b = bestQuote(s.quotes);
            if (b) m.set(s.id, { id: s.id, price: b.price, bookmaker: b.bookmaker, prob: s.modelProb, fairProb: s.fairProb, kickoff: e.kickoff });
          }
      setLatest(m);
    });
    return () => {
      alive = false;
    };
  }, [provider, revision]);

  const priced = useMemo(() => reprice(legs, latest), [legs, latest]);

  const update = useCallback((next: CouponLeg[]) => {
    setLegs(next);
    save(next);
  }, []);

  // reminders follow the coupon (APK only; no-op on the web)
  useEffect(() => {
    void scheduleCouponReminders(legs, settings.notifications.couponReminders);
  }, [legs, settings.notifications.couponReminders]);

  const value = useMemo<CouponValue>(
    () => ({
      legs: priced,
      has: (id) => legs.some((l) => l.selectionId === id),
      toggle: (event, sel) => {
        if (legs.some((l) => l.selectionId === sel.id)) {
          update(removeLeg(legs, sel.id));
          return null;
        }
        if (Date.parse(event.kickoff) <= Date.now()) return "Mecz już się rozpoczął — nie dodajemy go do kuponu.";
        if (!bestQuote(sel.quotes)) return "Brak aktualnego kursu dla tej selekcji.";
        try {
          const r = addLeg(legs, legFrom(event, sel));
          update(r.legs);
          return r.replaced ? `Zamieniono „${r.replaced.label}” — zdarzenia z jednego meczu są ze sobą powiązane, więc kupon przyjmuje jeden typ na mecz.` : null;
        } catch (e) {
          return (e as Error).message;
        }
      },
      remove: (id) => update(removeLeg(legs, id)),
      addMany: (items) => {
        let next = legs;
        let added = 0;
        for (const { event, sel } of items) {
          if (next.some((l) => l.selectionId === sel.id) || Date.parse(event.kickoff) <= Date.now() || !bestQuote(sel.quotes)) continue;
          try {
            next = addLeg(next, legFrom(event, sel)).legs;
            added += 1;
          } catch {
            break; // coupon full
          }
        }
        if (added) update(next);
        return added;
      },
      clear: () => update([]),
      open,
      setOpen,
    }),
    [priced, legs, update, open],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCoupon(): CouponValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useCoupon must be used inside CouponProvider");
  return v;
}
