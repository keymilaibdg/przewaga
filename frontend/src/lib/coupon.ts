// Coupon (accumulator) maths. The app never suggests that an accumulator is safer: every leg multiplies the
// bookmaker's margin, and the combined probability is the product of the legs' probabilities, which is valid only
// for independent events. Two selections from the same match are correlated, so one leg per match is allowed.
import type { MarketType, Sport } from "../types/domain";

export interface CouponLeg {
  selectionId: string;
  eventId: string;
  eventLabel: string;
  league: string;
  sport: Sport;
  kickoff: string;
  market: MarketType;
  label: string;
  price: number;
  bookmaker: string;
  /** Final probability shown by the app (model blended with the margin-free market). */
  prob: number;
  /** Margin-free market probability. */
  fairProb: number;
  addedAt: string;
}

export interface AddResult {
  legs: CouponLeg[];
  /** Leg removed because it came from the same match (correlated selections are not combined). */
  replaced: CouponLeg | null;
}

export const MAX_LEGS = 12;

export function addLeg(legs: CouponLeg[], leg: CouponLeg): AddResult {
  const same = legs.find((l) => l.eventId === leg.eventId) ?? null;
  const rest = legs.filter((l) => l.eventId !== leg.eventId);
  if (!same && rest.length >= MAX_LEGS) throw new RangeError(`Kupon może mieć najwyżej ${MAX_LEGS} zdarzeń`);
  return { legs: [...rest, leg], replaced: same && same.selectionId !== leg.selectionId ? same : null };
}

export function removeLeg(legs: CouponLeg[], selectionId: string): CouponLeg[] {
  return legs.filter((l) => l.selectionId !== selectionId);
}

export interface CouponSummary {
  legs: number;
  /** Product of the leg prices. */
  odds: number;
  /** Probability that every leg wins (independence assumed). */
  prob: number;
  /** Price at which the coupon would have zero expected value (1 / prob). */
  fairOdds: number;
  /** Expected value per 1 unit staked, without and with the stake tax. */
  ev: number;
  evTaxed: number;
  /** Bookmaker margin of the whole coupon vs the margin-free market, and the average per leg. */
  margin: number;
  avgLegMargin: number;
  stake: number;
  /** Payout if every leg wins, after the stake tax. */
  payout: number;
  /** Expected profit (negative = expected loss) in money for `stake`. */
  expectedProfit: number;
}

export function summarize(legs: CouponLeg[], stake: number, stakeTax: number): CouponSummary {
  const odds = legs.reduce((s, l) => s * l.price, 1);
  const prob = legs.reduce((s, l) => s * l.prob, 1);
  const marketProb = legs.reduce((s, l) => s * l.fairProb, 1);
  const legMargins = legs.map((l) => 1 / (l.price * l.fairProb) - 1);
  const payout = stake * (1 - stakeTax) * odds;
  return {
    legs: legs.length,
    odds,
    prob,
    fairOdds: prob > 0 ? 1 / prob : Infinity,
    ev: prob * odds - 1,
    evTaxed: prob * odds * (1 - stakeTax) - 1,
    margin: legs.length ? 1 / (odds * marketProb) - 1 : 0,
    avgLegMargin: legMargins.length ? legMargins.reduce((a, b) => a + b, 0) / legMargins.length : 0,
    stake,
    payout,
    expectedProfit: legs.length ? prob * payout - stake : 0,
  };
}

/** Selection data the coupon needs from the latest published events. */
export interface PricedSelection {
  id: string;
  price: number;
  bookmaker: string;
  prob: number;
  fairProb: number;
  kickoff: string;
}

export type LegState = "ok" | "started" | "missing" | "price_changed";

export interface RepricedLeg {
  leg: CouponLeg;
  state: LegState;
  previousPrice: number | null;
}

/**
 * Refresh legs with the newest prices. A leg whose match has started is kept but flagged; a selection that is
 * no longer offered is flagged as missing (its last known price stays, it cannot be relied on).
 */
export function reprice(legs: CouponLeg[], latest: Map<string, PricedSelection>, now = Date.now()): RepricedLeg[] {
  return legs.map((leg) => {
    const s = latest.get(leg.selectionId);
    const kickoff = Date.parse(s?.kickoff ?? leg.kickoff);
    if (kickoff <= now) return { leg, state: "started", previousPrice: null };
    if (!s) return { leg, state: "missing", previousPrice: null };
    const changed = Math.abs(s.price - leg.price) >= 0.005;
    return {
      leg: { ...leg, price: s.price, bookmaker: s.bookmaker, prob: s.prob, fairProb: s.fairProb, kickoff: s.kickoff },
      state: changed ? "price_changed" : "ok",
      previousPrice: changed ? leg.price : null,
    };
  });
}
