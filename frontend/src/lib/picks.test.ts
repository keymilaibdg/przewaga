import { test } from "node:test";
import assert from "node:assert/strict";
import { appPicks, pickFor } from "./picks.ts";
import type { SportEvent } from "../types/domain";

const NOW = Date.parse("2030-01-01T10:00:00Z");

function sel(id: string, label: string, price: number, prob: number) {
  return { id, market: "1X2", label, line: null, quotes: [{ bookmaker: "b", price, updatedAt: "" }], modelProb: prob, probLow: prob, probHigh: prob, fairProb: prob, priceHistory: [] };
}

function ev(id: string, kickoff: string, sels: ReturnType<typeof sel>[], recSel?: string): SportEvent {
  return {
    id,
    sport: "football",
    kickoff,
    markets: [{ market: "1X2", name: "1X2", margin: 0.05, available: true, verdict: "", selections: sels }],
    recommendations: recSel ? [{ id: "r", selectionId: recSel, status: "active" }] : [],
  } as unknown as SportEvent;
}

test("most likely outcome within the price range", () => {
  const e = ev("e1", "2030-01-01T18:00:00Z", [sel("h", "1", 1.1, 0.88), sel("d", "X", 7, 0.1), sel("a", "2", 2.5, 0.38), sel("x", "X2", 1.6, 0.6)]);
  const p = pickFor(e, 0.12, NOW)!;
  assert.equal(p.selection.id, "x"); // 1.10 is below the minimum price
  assert.ok(Math.abs(p.evTaxed - (0.6 * 1.6 * 0.88 - 1)) < 1e-9);
  assert.equal(p.value, null);
});

test("an active recommendation wins and is listed first", () => {
  const a = ev("a", "2030-01-01T18:00:00Z", [sel("a1", "1", 1.5, 0.66), sel("a2", "2", 4, 0.24)]);
  const b = ev("b", "2030-01-01T18:00:00Z", [sel("b1", "1", 2.2, 0.45), sel("b2", "2", 3.4, 0.3)], "b2");
  const picks = appPicks([a, b], { sports: ["football"], stakeTax: 0.12 }, NOW);
  assert.deepEqual(picks.map((p) => p.selection.id), ["b2", "a1"]);
  assert.ok(picks[0].value);
});

test("no pick for a match about to start or without odds", () => {
  assert.equal(pickFor(ev("s", "2030-01-01T10:10:00Z", [sel("s1", "1", 1.5, 0.66)]), 0.12, NOW), null);
  assert.equal(pickFor(ev("n", "2030-01-01T18:00:00Z", []), 0.12, NOW), null);
});
