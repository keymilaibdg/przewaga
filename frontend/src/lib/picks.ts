// "Propozycje aplikacji": one pick per match, so a coupon can be built quickly.
// A pick is either a real edge (an active recommendation: model or market mode) or, when there is none, the most
// likely outcome according to the margin-free market. The second kind has no edge over the bookmaker and the app
// says so next to it (EV after tax is shown, usually negative).
import { bestQuote } from "./odds.ts";
import type { MarketAnalysis, MarketType, Recommendation, SelectionAnalysis, SportEvent } from "../types/domain";

export interface AppPick {
  event: SportEvent;
  market: MarketAnalysis;
  selection: SelectionAnalysis;
  price: number;
  bookmaker: string;
  prob: number;
  ev: number;
  evTaxed: number;
  /** An active recommendation (model or market mode) backs this pick. */
  value: Recommendation | null;
}

const PICK_MARKETS: MarketType[] = ["1X2", "MONEYLINE", "TOTAL_GOALS", "TOTAL_POINTS", "SPREAD"];
export const PICK_MIN_PRICE = 1.2;
export const PICK_MAX_PRICE = 3.0;

export function pickFor(e: SportEvent, stakeTax: number, now = Date.now()): AppPick | null {
  if (Date.parse(e.kickoff) - now < 30 * 60_000) return null;
  const rec = e.recommendations.find((r) => r.status === "active") ?? null;
  let best: AppPick | null = null;
  for (const m of e.markets) {
    if (!m.available || !PICK_MARKETS.includes(m.market)) continue;
    for (const s of m.selections) {
      const q = bestQuote(s.quotes);
      if (!q) continue;
      const isRec = rec !== null && rec.selectionId === s.id;
      if (!isRec && (q.price < PICK_MIN_PRICE || q.price > PICK_MAX_PRICE)) continue;
      const pick: AppPick = {
        event: e,
        market: m,
        selection: s,
        price: q.price,
        bookmaker: q.bookmaker,
        prob: s.modelProb,
        ev: s.modelProb * q.price - 1,
        evTaxed: s.modelProb * q.price * (1 - stakeTax) - 1,
        value: isRec ? rec : null,
      };
      if (isRec) return pick;
      if (!best || pick.prob > best.prob) best = pick;
    }
  }
  return best;
}

/** One pick per match: backed picks first, then the most likely outcomes. */
export function appPicks(events: SportEvent[], opts: { sports: string[]; stakeTax: number; limit?: number; withinHours?: number }, now = Date.now()): AppPick[] {
  const horizon = (opts.withinHours ?? 7 * 24) * 3_600_000;
  return events
    .filter((e) => opts.sports.includes(e.sport) && Date.parse(e.kickoff) - now <= horizon)
    .map((e) => pickFor(e, opts.stakeTax, now))
    .filter((p): p is AppPick => p !== null)
    .sort((a, b) => Number(!!b.value) - Number(!!a.value) || b.prob - a.prob)
    .slice(0, opts.limit ?? 10);
}
