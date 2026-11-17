// Performance aggregation from history entries (used for both DEMO and live data).
// Withdrawn recommendations are kept in history but excluded from all performance figures.
import type { CalibrationBin, HistoryEntry, MarketType, PerformanceSlice, PerformanceSummary } from "../types/domain";
import { closingLineValue } from "../lib/odds";

const MARKET_GROUP: Record<MarketType, string> = {
  "1X2": "1X2 / Moneyline",
  MONEYLINE: "1X2 / Moneyline",
  DOUBLE_CHANCE: "Podwójna szansa / DNB",
  DRAW_NO_BET: "Podwójna szansa / DNB",
  TOTAL_GOALS: "Over/Under",
  TOTAL_POINTS: "Over/Under",
  TEAM_TOTAL: "Gole/punkty drużyny",
  TEAM_POINTS: "Gole/punkty drużyny",
  BTTS: "BTTS",
  ASIAN_HANDICAP: "Handicap",
  SPREAD: "Handicap",
  CORNERS: "Rzuty rożne",
  CARDS: "Kartki",
  PLAYER_PROPS: "Zawodnicy",
};

function slice(entries: HistoryEntry[], key: string, label: string): PerformanceSlice {
  const settled = entries.filter((e) => e.result !== "pending" && e.result !== "withdrawn");
  const staked = settled.filter((e) => e.result !== "void").length;
  const profit = settled.reduce((s, e) => s + e.profit, 0);
  return {
    key,
    label,
    bets: settled.length,
    won: settled.filter((e) => e.result === "won" || e.result === "half_won").length,
    roi: staked ? profit / staked : 0,
    yieldPct: staked ? (profit / staked) * 100 : 0,
  };
}

function groupBy(entries: HistoryEntry[], fn: (e: HistoryEntry) => string): Map<string, HistoryEntry[]> {
  const m = new Map<string, HistoryEntry[]>();
  for (const e of entries) {
    const k = fn(e);
    m.set(k, [...(m.get(k) ?? []), e]);
  }
  return m;
}

export function computePerformance(all: HistoryEntry[], scope: "live" | "backtest"): PerformanceSummary {
  const entries = all.filter((e) => e.result !== "withdrawn");
  const settled = entries.filter((e) => e.result !== "pending");
  const decided = settled.filter((e) => e.result !== "void");
  const profit = settled.reduce((s, e) => s + e.profit, 0);
  const won = settled.filter((e) => e.result === "won" || e.result === "half_won").length;

  let running = 0;
  const cumulative = [...settled]
    .sort((a, b) => Date.parse(a.kickoff) - Date.parse(b.kickoff))
    .map((e) => {
      running += e.profit;
      return { at: e.kickoff, profit: running };
    });

  const bins: CalibrationBin[] = [];
  for (let lo = 0.3; lo < 0.9; lo += 0.1) {
    const inBin = decided.filter((e) => e.modelProb >= lo && e.modelProb < lo + 0.1);
    if (inBin.length < 8) continue;
    bins.push({
      predicted: inBin.reduce((s, e) => s + e.modelProb, 0) / inBin.length,
      observed: inBin.filter((e) => e.result === "won").length / inBin.length,
      count: inBin.length,
    });
  }

  const withClose = settled.filter((e) => e.closingPrice);
  const sportLabel = { football: "Piłka nożna", basketball: "Koszykówka" } as const;
  const riskLabel = { low: "Niskie ryzyko", medium: "Średnie ryzyko", high: "Wysokie ryzyko" } as const;

  return {
    scope,
    bets: entries.length,
    settled: settled.length,
    won,
    lost: settled.filter((e) => e.result === "lost" || e.result === "half_lost").length,
    voided: settled.filter((e) => e.result === "void").length,
    pending: entries.length - settled.length,
    staked: decided.length,
    profit,
    roi: decided.length ? profit / decided.length : 0,
    hitRate: decided.length ? won / decided.length : 0,
    avgPrice: decided.length ? decided.reduce((s, e) => s + e.openingPrice, 0) / decided.length : 0,
    avgClv: withClose.length ? withClose.reduce((s, e) => s + closingLineValue(e.openingPrice, e.closingPrice!), 0) / withClose.length : null,
    cumulative,
    bySport: [...groupBy(entries, (e) => e.sport)].map(([k, v]) => slice(v, k, sportLabel[k as keyof typeof sportLabel])),
    byMarket: [...groupBy(entries, (e) => MARKET_GROUP[e.market])].map(([k, v]) => slice(v, k, k)).sort((a, b) => b.bets - a.bets),
    byRisk: (["low", "medium", "high"] as const).map((r) => slice(entries.filter((e) => e.risk === r), r, riskLabel[r])),
    calibration: bins,
    brier: decided.length ? decided.reduce((s, e) => s + (e.modelProb - (e.result === "won" ? 1 : 0)) ** 2, 0) / decided.length : null,
  };
}
