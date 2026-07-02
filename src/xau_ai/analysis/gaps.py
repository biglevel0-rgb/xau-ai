"""Fair Value Gap (FVG) detection.

An FVG is a 3-candle imbalance: the wick of candle ``i`` and candle ``i-2`` do
not overlap, leaving an untraded price range.

* **Bullish** FVG: ``low[i] > high[i-2]`` — gap sits below the market as support.
* **Bearish** FVG: ``high[i] < low[i-2]`` — gap sits above the market as resistance.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from xau_ai.core.models import Candle


@dataclass(frozen=True, slots=True)
class FairValueGap:
    """An imbalance anchored at the third candle (``index``)."""

    index: int
    kind: Literal["bullish", "bearish"]
    top: float
    bottom: float

    @property
    def size(self) -> float:
        """Height of the gap (always non-negative)."""
        return self.top - self.bottom


def find_fvgs(candles: Sequence[Candle]) -> list[FairValueGap]:
    """Return all FVGs in ``candles``, ordered by index (oldest first)."""
    gaps: list[FairValueGap] = []
    for i in range(2, len(candles)):
        first = candles[i - 2]
        third = candles[i]
        if third.low > first.high:
            gaps.append(FairValueGap(i, "bullish", top=third.low, bottom=first.high))
        elif first.low > third.high:
            gaps.append(FairValueGap(i, "bearish", top=first.low, bottom=third.high))
    return gaps
