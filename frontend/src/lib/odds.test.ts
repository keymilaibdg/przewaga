import { test } from "node:test";
import assert from "node:assert/strict";
import {
  bestQuote,
  closingLineValue,
  expectedValue,
  fairPrice,
  fairProbabilities,
  impliedProbability,
  kellyFraction,
  minPriceWithTax,
  overround,
} from "./odds.ts";

const close = (a: number, b: number, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test("implied probability of 1.35 is 74.07%", () => close(impliedProbability(1.35), 0.7407407407));
test("implied probability rejects prices <= 1", () => assert.throws(() => impliedProbability(1)));

test("overround of a 1X2 market", () => {
  // 1/2.10 + 1/3.40 + 1/3.60 = 0.476190 + 0.294118 + 0.277778 = 1.048086
  close(overround([2.1, 3.4, 3.6]), 0.0480859, 1e-6);
});

test("fair probabilities sum to 1 and keep ordering", () => {
  const fair = fairProbabilities([2.1, 3.4, 3.6]);
  close(fair.reduce((a, b) => a + b, 0), 1);
  assert.ok(fair[0] > fair[1] && fair[1] > fair[2]);
  close(fair[0], 0.476190476 / 1.048085901, 1e-8);
});

test("EV from the brief example: p=0.82 @1.35 is +10.7%", () => close(expectedValue(0.82, 1.35), 0.107));
test("EV is negative when model p is below implied", () => assert.ok(expectedValue(0.7, 1.35) < 0));
test("EV is zero at fair price", () => close(expectedValue(0.5, fairPrice(0.5)), 0));
test("EV rejects invalid probability", () => assert.throws(() => expectedValue(1.2, 2)));

test("Kelly is zero for negative EV and positive otherwise", () => {
  assert.equal(kellyFraction(0.4, 2.0), 0);
  close(kellyFraction(0.55, 2.0), 0.1);
});

test("Polish 12% stake tax raises the break-even price", () => {
  // p = 0.5: fair price 2.00, with 12% tax 2.2727
  close(minPriceWithTax(0.5, 0.12), 2.272727, 1e-6);
  close(minPriceWithTax(0.5, 0), 2);
  close(expectedValue(0.5, minPriceWithTax(0.5, 0.12)) * 0.88 + 0.88 - 1, 0, 1e-9);
  assert.throws(() => minPriceWithTax(0.5, 1));
});

test("CLV positive when taken price beats close", () => close(closingLineValue(2.1, 2.0), 0.05));

test("bestQuote picks highest price and handles empty list", () => {
  assert.equal(bestQuote([{ price: 1.9 }, { price: 2.05 }, { price: 2.0 }])?.price, 2.05);
  assert.equal(bestQuote([]), null);
});
