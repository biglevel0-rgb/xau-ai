"""Numeric indicators: EMA, ATR, and a clamp helper.

All functions are pure and operate on plain sequences / candles so they can be
unit-tested in isolation and reused across skills (DRY).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import fmean

from xau_ai.core.models import Candle


def clamp01(value: float) -> float:
    """Clamp ``value`` into the closed interval ``[0.0, 1.0]``."""
    return max(0.0, min(1.0, value))


def correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Pearson correlation of two equal-length series (0.0 if either is constant)."""
    if len(xs) != len(ys):
        raise ValueError("series must be the same length")
    if len(xs) < 2:
        raise ValueError("need at least two points")
    mean_x = fmean(xs)
    mean_y = fmean(ys)
    cov = math.fsum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    var_x = math.fsum((x - mean_x) ** 2 for x in xs)
    var_y = math.fsum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0.0 or var_y <= 0.0:
        return 0.0
    return cov / math.sqrt(var_x * var_y)


def vwap(candles: Sequence[Candle]) -> float:
    """Volume-weighted average price over ``candles`` (typical price = HLC/3)."""
    numerator = 0.0
    denominator = 0.0
    for candle in candles:
        typical = (candle.high + candle.low + candle.close) / 3.0
        numerator += typical * candle.volume
        denominator += candle.volume
    if denominator <= 0.0:
        raise ValueError("total volume must be positive to compute VWAP")
    return numerator / denominator


def ema(values: Sequence[float], period: int) -> list[float]:
    """Exponential moving average, one output per input (seeded with values[0])."""
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    if not values:
        return []
    k = 2.0 / (period + 1)
    out = [values[0]]
    for value in values[1:]:
        out.append(value * k + out[-1] * (1.0 - k))
    return out


def atr(candles: Sequence[Candle], period: int) -> float:
    """Average True Range (Wilder's smoothing). Needs at least ``period+1`` bars."""
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    if len(candles) < period + 1:
        raise ValueError(f"need at least {period + 1} candles, got {len(candles)}")

    true_ranges: list[float] = []
    prev_close = candles[0].close
    for candle in candles[1:]:
        true_ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - prev_close),
                abs(candle.low - prev_close),
            )
        )
        prev_close = candle.close

    atr_value = sum(true_ranges[:period]) / period
    for true_range in true_ranges[period:]:
        atr_value = (atr_value * (period - 1) + true_range) / period
    return atr_value
