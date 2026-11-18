import type { Recommendation, RiskLevel, SportEvent, UserSettings } from "../types/domain";

const RISK_ORDER: Record<RiskLevel, number> = { low: 0, medium: 1, high: 2 };

/** Active recommendations that pass the user's own thresholds (on top of the engine's gate). */
export function visibleRecs(evt: SportEvent, s: UserSettings): Recommendation[] {
  if (!s.sports.includes(evt.sport)) return [];
  return evt.recommendations.filter(
    (r) =>
      r.status === "active" &&
      (s.marketMode !== false || r.kind !== "market") &&
      r.quality >= s.minQuality &&
      r.ev >= s.minEv &&
      RISK_ORDER[r.risk] <= RISK_ORDER[s.maxRisk] &&
      !s.excludedBookmakers.includes(r.bookmaker),
  );
}

/** Sort key for "atrakcyjność okazji": quality first, then EV. */
export function attractiveness(evt: SportEvent, s: UserSettings): number {
  const best = visibleRecs(evt, s)[0];
  return best ? best.quality + best.ev * 100 : -1;
}

export interface TopTip {
  event: SportEvent;
  rec: Recommendation;
}

export function topTips(events: SportEvent[], s: UserSettings, limit = 10): TopTip[] {
  return events
    .flatMap((event) => visibleRecs(event, s).map((rec) => ({ event, rec })))
    .sort((a, b) => b.rec.quality - a.rec.quality || b.rec.ev - a.rec.ev)
    .slice(0, limit);
}

export function oddsFreshness(evt: SportEvent) {
  return evt.sources.find((x) => x.kind === "odds")?.freshness ?? "missing";
}
