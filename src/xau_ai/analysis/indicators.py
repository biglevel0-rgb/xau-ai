"""Numeric indicators: EMA, ATR, and a clamp helper.

All functions are pure and operate on plain sequences / candles so they can be
unit-tested in isolation and reused across skills (DRY).
"""

from __future__ import annotations

from collections.abc import Sequence

from xau_ai.core.models import Candle


def clamp01(value: float) -> float:
    """Clamp ``value`` into the closed interval ``[0.0, 1.0]``."""
    return max(0.0, min(1.0, value))


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
