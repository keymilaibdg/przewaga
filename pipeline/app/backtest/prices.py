"""How did selections priced at a given level actually do? ("Is 1.30 a trap?")

For every historical match with odds, each 1X2 / moneyline selection is put in a price bucket by its market-average
price. Per bucket: number of selections, how often they won (with a 95% interval), the probability the price
implied, and the return of betting all of them at the average price, at the best price and after the Polish 12%
stake tax. Model-free: it describes the market, so all seasons are used.
"""
from __future__ import annotations

import math
from collections import defaultdict

from .evaluate import Row

BUCKETS: tuple[tuple[float, float], ...] = (
    (1.01, 1.15), (1.15, 1.25), (1.25, 1.35), (1.35, 1.45), (1.45, 1.60), (1.60, 1.80),
    (1.80, 2.10), (2.10, 2.60), (2.60, 3.50), (3.50, 6.00), (6.00, 51.0),
)
TAX = 0.12


def bucket_of(price: float) -> tuple[float, float] | None:
    return next((b for b in BUCKETS if b[0] <= price < b[1]), None)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def price_buckets(rows: list[Row]) -> list[dict]:
    acc: dict[tuple[float, float], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r.market != "h2h" or r.outcome < 0:
            continue
        prices = r.avg or r.ref
        fair = r.p_fair
        for i, p in enumerate(prices):
            b = bucket_of(p)
            if b is None:
                continue
            won = 1.0 if r.outcome == i else 0.0
            a = acc[b]
            a["won"].append(won)
            a["price"].append(p)
            a["fair"].append(fair[i])
            a["ret_avg"].append(won * p - 1)
            a["ret_best"].append(won * r.best[i] - 1)
            a["ret_tax"].append(won * p * (1 - TAX) - 1)
    out = []
    for b in BUCKETS:
        a = acc.get(b)
        if not a or len(a["won"]) < 20:
            continue
        n, k = len(a["won"]), int(sum(a["won"]))
        lo, hi = wilson(k, n)
        mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
        out.append(
            {
                "from": b[0],
                "to": b[1],
                "n": n,
                "wins": k,
                "winRate": round(k / n, 4),
                "winRateLow": round(lo, 4),
                "winRateHigh": round(hi, 4),
                "avgPrice": round(mean(a["price"]), 3),
                "implied": round(mean([1 / p for p in a["price"]]), 4),
                "fair": round(mean(a["fair"]), 4),
                "roiAvg": round(mean(a["ret_avg"]), 4),
                "roiBest": round(mean(a["ret_best"]), 4),
                "roiTaxed": round(mean(a["ret_tax"]), 4),
            }
        )
    return out


def summary(rows: list[Row], source: str) -> dict:
    seasons = sorted({r.season for r in rows if r.market == "h2h"})
    return {"seasons": seasons, "matches": len({r.event_id for r in rows if r.market == "h2h"}), "source": source, "buckets": price_buckets(rows)}
