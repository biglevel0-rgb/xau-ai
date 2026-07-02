"""Volume skill.

Direction comes from price relative to VWAP (above = LONG bias, below = SHORT).
Conviction blends how far price sits from VWAP (in ATR) with the current volume
surge versus the window average. Only OHLCV is available, so no bid/ask delta or
footprint is attempted.
"""

from __future__ import annotations

from statistics import fmean
from typing import ClassVar

from xau_ai.analysis.indicators import atr, clamp01, vwap
from xau_ai.core.models import Direction, MarketContext, SkillResult, Timeframe
from xau_ai.core.registry import registry
from xau_ai.skills.base import BaseSkill


@registry.register
class VolumeSkill(BaseSkill):
    """VWAP-based directional bias with a volume-surge conviction factor."""

    name: ClassVar[str] = "volume"

    def __init__(
        self,
        timeframe: Timeframe = Timeframe.M5,
        atr_period: int = 14,
        window: int = 20,
        min_dist_atr: float = 0.1,
    ) -> None:
        self._tf = timeframe
        self._atr_period = atr_period
        self._window = window
        self._min_dist_atr = min_dist_atr

    def _neutral(self, reason: str, score: float = 0.0) -> SkillResult:
        return SkillResult(
            skill_name=self.name,
            direction=Direction.NEUTRAL,
            score=clamp01(score),
            evidence=(reason,),
        )

    def analyze(self, ctx: MarketContext) -> SkillResult:
        candles = ctx.candles(self._tf)
        if len(candles) < self._atr_period + 1:
            return self._neutral(f"insufficient data ({len(candles)} bars)")

        window = candles[-self._window :]
        try:
            vwap_value = vwap(window)
        except ValueError:
            return self._neutral("no volume (cannot compute VWAP)")

        atr_value = max(atr(candles, self._atr_period), 1e-9)
        last = candles[-1]
        dist = (last.close - vwap_value) / atr_value

        if abs(dist) < self._min_dist_atr:
            return self._neutral("price at VWAP", abs(dist) / self._min_dist_atr * 0.3)

        avg_volume = fmean(c.volume for c in window)
        surge = last.volume / avg_volume if avg_volume > 0 else 0.0
        strength = clamp01(abs(dist))
        conviction = clamp01(surge / 2.0)
        score = clamp01(0.5 * strength + 0.5 * conviction)

        direction = Direction.LONG if dist > 0 else Direction.SHORT
        side = "above" if dist > 0 else "below"
        return SkillResult(
            skill_name=self.name,
            direction=direction,
            score=score,
            evidence=(
                f"price {side} VWAP",
                f"{abs(dist):.2f} ATR from VWAP",
                f"volume surge {surge:.2f}x",
            ),
            meta={"vwap": vwap_value, "dist_atr": dist, "surge": surge},
        )
