import { test } from "node:test";
import assert from "node:assert/strict";
import { addLeg, MAX_LEGS, removeLeg, reprice, summarize, type CouponLeg } from "./coupon.ts";

const close = (a: number, b: number, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

const leg = (i: number, over: Partial<CouponLeg> = {}): CouponLeg => ({
  selectionId: `e${i}:h2h:home:null`,
  eventId: `e${i}`,
  eventLabel: `A${i} – B${i}`,
  league: "Premier League",
  sport: "football",
  kickoff: "2030-01-01T20:00:00Z",
  market: "1X2",
  label: `Wygrana A${i}`,
  price: 2.0,
  bookmaker: "x",
  prob: 0.5,
  fairProb: 0.48,
  addedAt: "2030-01-01T10:00:00Z",
  ...over,
});

test("one leg per match: a second selection from the same match replaces the first", () => {
  let legs: CouponLeg[] = [];
  legs = addLeg(legs, leg(1)).legs;
  const r = addLeg(legs, leg(1, { selectionId: "e1:totals:over:2.5", label: "Powyżej 2,5" }));
  assert.equal(r.legs.length, 1);
  assert.equal(r.legs[0].label, "Powyżej 2,5");
  assert.equal(r.replaced?.label, "Wygrana A1");
  assert.equal(addLeg(r.legs, leg(1, { selectionId: "e1:totals:over:2.5" })).replaced, null);
});

test("coupon size is limited", () => {
  let legs: CouponLeg[] = [];
  for (let i = 0; i < MAX_LEGS; i++) legs = addLeg(legs, leg(i)).legs;
  assert.throws(() => addLeg(legs, leg(99)));
  assert.equal(removeLeg(legs, leg(0).selectionId).length, MAX_LEGS - 1);
});

test("odds and probability multiply, EV and tax", () => {
  const s = summarize([leg(1, { price: 2.0, prob: 0.5 }), leg(2, { price: 1.5, prob: 0.6 })], 10, 0.12);
  close(s.odds, 3.0);
  close(s.prob, 0.3);
  close(s.fairOdds, 1 / 0.3);
  close(s.ev, 0.3 * 3 - 1);
  close(s.evTaxed, 0.3 * 3 * 0.88 - 1);
  close(s.payout, 10 * 0.88 * 3);
  close(s.expectedProfit, 0.3 * 26.4 - 10);
});

test("bookmaker margin compounds with every leg", () => {
  // each leg: price 1.9 on a 50% event -> 5.26% margin per leg
  const legs = [1, 2, 3, 4].map((i) => leg(i, { price: 1.9, prob: 0.5, fairProb: 0.5 }));
  const one = summarize(legs.slice(0, 1), 1, 0);
  const four = summarize(legs, 1, 0);
  close(one.margin, 1 / 0.95 - 1);
  close(four.margin, 1 / 0.95 ** 4 - 1);
  assert.ok(four.margin > 3 * one.margin);
  assert.ok(four.ev < one.ev);
});

test("empty coupon", () => {
  const s = summarize([], 10, 0.12);
  assert.equal(s.legs, 0);
  assert.equal(s.expectedProfit, 0);
});

test("reprice flags started, missing and changed legs", () => {
  const now = Date.parse("2030-01-01T12:00:00Z");
  const legs = [leg(1), leg(2), leg(3, { kickoff: "2030-01-01T11:00:00Z" })];
  const latest = new Map([
    [leg(1).selectionId, { id: leg(1).selectionId, price: 2.1, bookmaker: "y", prob: 0.47, fairProb: 0.46, kickoff: leg(1).kickoff }],
  ]);
  const r = reprice(legs, latest, now);
  assert.deepEqual(r.map((x) => x.state), ["price_changed", "missing", "started"]);
  assert.equal(r[0].leg.price, 2.1);
  assert.equal(r[0].previousPrice, 2.0);
  assert.equal(r[1].leg.price, 2.0);
});
