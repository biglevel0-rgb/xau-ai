"""Fair Value Gap skill.

Direction comes from the most recent significant FVG (bullish gap = LONG bias,
bearish gap = SHORT bias). Confidence blends the gap size (in ATR units) with
its recency; tiny gaps are treated as noise and ignored.
"""

from __future__ import annotations

from typing import ClassVar

from xau_ai.analysis.gaps import find_fvgs
from xau_ai.analysis.indicators import atr, clamp01
from xau_ai.core.models import Direction, MarketContext, SkillResult, Timeframe
from xau_ai.core.registry import registry
from xau_ai.skills.base import BaseSkill


@registry.register
class FvgSkill(BaseSkill):
    """Detect the latest Fair Value Gap and score it."""

    name: ClassVar[str] = "fvg"

    def __init__(
        self,
        timeframe: Timeframe = Timeframe.M5,
        atr_period: int = 14,
        recency_window: int = 20,
        min_size_atr: float = 0.1,
    ) -> None:
        self._tf = timeframe
        self._atr_period = atr_period
        self._recency_window = recency_window
        self._min_size_atr = min_size_atr

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

        gaps = find_fvgs(candles)
        if not gaps:
            return self._neutral("no FVG detected")

        gap = gaps[-1]
        atr_value = max(atr(candles, self._atr_period), 1e-9)
        size_atr = gap.size / atr_value
        if size_atr < self._min_size_atr:
            return self._neutral("FVG below significance threshold")

        direction = Direction.LONG if gap.kind == "bullish" else Direction.SHORT
        age = (len(candles) - 1) - gap.index
        recency = clamp01(1.0 - age / self._recency_window)
        strength = clamp01(size_atr)
        score = clamp01(0.5 * strength + 0.5 * recency)

        filled = any(c.low <= gap.top and c.high >= gap.bottom for c in candles[gap.index + 1 :])
        side = "below" if direction is Direction.LONG else "above"
        level = gap.bottom if direction is Direction.LONG else gap.top
        return SkillResult(
            skill_name=self.name,
            direction=direction,
            score=score,
            evidence=(
                f"{gap.kind.capitalize()} FVG",
                f"size {size_atr:.2f} ATR",
                "mitigated" if filled else "unfilled",
            ),
            invalidation=f"close {side} {level:.2f}",
            meta={"size_atr": size_atr, "age": float(age), "filled": 1.0 if filled else 0.0},
        )
