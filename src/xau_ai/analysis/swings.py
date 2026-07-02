"""Swing-point (fractal pivot) detection.

A swing high at index ``i`` has a strictly higher high than the ``left`` bars
before and ``right`` bars after it; a swing low is the mirror. Strict
inequalities avoid ambiguous flat plateaus.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from xau_ai.core.models import Candle


@dataclass(frozen=True, slots=True)
class SwingPoint:
    """A confirmed pivot high or low."""

    index: int
    timestamp: datetime
    price: float
    kind: Literal["high", "low"]


def find_swings(candles: Sequence[Candle], left: int = 2, right: int = 2) -> list[SwingPoint]:
    """Return swing points in ``candles``, ordered by index.

    A pivot needs ``left`` bars before and ``right`` bars after to confirm, so
    the first ``left`` and last ``right`` candles can never be swings.
    """
    if left < 1 or right < 1:
        raise ValueError("left and right must be >= 1")

    swings: list[SwingPoint] = []
    n = len(candles)
    for i in range(left, n - right):
        pivot = candles[i]
        window = range(i - left, i + right + 1)

        if all(pivot.high > candles[j].high for j in window if j != i):
            swings.append(SwingPoint(i, pivot.timestamp, pivot.high, "high"))
        if all(pivot.low < candles[j].low for j in window if j != i):
            swings.append(SwingPoint(i, pivot.timestamp, pivot.low, "low"))
    return swings
