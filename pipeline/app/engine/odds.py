"""Odds math. Mirrors frontend/src/lib/odds.ts — keep test cases in sync."""
from __future__ import annotations


def implied_probability(price: float) -> float:
    if not price > 1:
        raise ValueError(f"Invalid decimal price: {price}")
    return 1 / price


def overround(prices: list[float]) -> float:
    if len(prices) < 2:
        raise ValueError("A market needs at least two selections")
    return sum(implied_probability(p) for p in prices) - 1


def fair_probabilities(prices: list[float]) -> list[float]:
    raw = [implied_probability(p) for p in prices]
    total = sum(raw)
    return [p / total for p in raw]


def expected_value(probability: float, price: float) -> float:
    if not 0 <= probability <= 1:
        raise ValueError(f"Invalid probability: {probability}")
    return probability * price - 1


def kelly_fraction(probability: float, price: float) -> float:
    b = price - 1
    return max(0.0, (probability * b - (1 - probability)) / b)


def closing_line_value(taken: float, closing: float) -> float:
    return taken / closing - 1
