// Odds math. Mirrors backend/app/engine/odds.py — keep test cases in sync.

/** Implied probability of decimal odds (includes bookmaker margin). */
export function impliedProbability(price: number): number {
  if (!Number.isFinite(price) || price <= 1) throw new RangeError(`Invalid decimal price: ${price}`);
  return 1 / price;
}

/** Bookmaker overround for a complete market, e.g. 0.05 for 5%. */
export function overround(prices: number[]): number {
  if (prices.length < 2) throw new RangeError("A market needs at least two selections");
  return prices.reduce((sum, p) => sum + impliedProbability(p), 0) - 1;
}

/** Margin-free probabilities using proportional normalisation. */
export function fairProbabilities(prices: number[]): number[] {
  const raw = prices.map(impliedProbability);
  const total = raw.reduce((a, b) => a + b, 0);
  return raw.map((p) => p / total);
}

/** Expected value per 1 unit staked. */
export function expectedValue(probability: number, price: number): number {
  if (probability < 0 || probability > 1) throw new RangeError(`Invalid probability: ${probability}`);
  return probability * price - 1;
}

/** Decimal price at which the bet has zero EV for the given probability. */
export function fairPrice(probability: number): number {
  if (probability <= 0 || probability > 1) throw new RangeError(`Invalid probability: ${probability}`);
  return 1 / probability;
}

/** Full Kelly fraction; callers should apply a fractional multiplier. Never negative. */
export function kellyFraction(probability: number, price: number): number {
  const b = price - 1;
  const f = (probability * b - (1 - probability)) / b;
  return Math.max(0, f);
}

/** Closing line value: positive when we beat the closing price. */
export function closingLineValue(takenPrice: number, closingPrice: number): number {
  return takenPrice / closingPrice - 1;
}

/**
 * Minimum decimal price needed at a bookmaker that deducts `stakeTax` from the stake (Poland: 12%)
 * for the bet to reach `minEv`. EV with tax = p * price * (1 - tax) - 1.
 */
export function minPriceWithTax(probability: number, stakeTax: number, minEv = 0): number {
  if (probability <= 0 || probability > 1) throw new RangeError(`Invalid probability: ${probability}`);
  if (stakeTax < 0 || stakeTax >= 1) throw new RangeError(`Invalid tax: ${stakeTax}`);
  return (1 + minEv) / (probability * (1 - stakeTax));
}

/** Best (highest) price among quotes. */
export function bestQuote<T extends { price: number }>(quotes: T[]): T | null {
  return quotes.reduce<T | null>((best, q) => (best === null || q.price > best.price ? q : best), null);
}
