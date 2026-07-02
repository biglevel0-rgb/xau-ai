"""Volatility skill.

A tradeability filter (never directional): it compares short-term ATR to a
longer baseline. A dead, low-volatility market (chop) and an erratic, very
high-volatility market both score low; a normal regime scores high. Direction is
always NEUTRAL.
"""

from __future__ import annotations

from typing import ClassVar

from xau_ai.analysis.indicators import atr, clamp01
from xau_ai.core.models import Direction, MarketContext, SkillResult, Timeframe
from xau_ai.core.registry import registry
from xau_ai.skills.base import BaseSkill


@registry.register
class VolatilitySkill(BaseSkill):
    """Score the current volatility regime (short ATR vs long baseline)."""

    name: ClassVar[str] = "volatility"

    def __init__(
        self,
        timeframe: Timeframe = Timeframe.M5,
        short_period: int = 14,
        long_period: int = 50,
        low_ratio: float = 0.6,
        high_ratio: float = 1.8,
    ) -> None:
        if short_period >= long_period:
            raise ValueError("short_period must be shorter than long_period")
        self._tf = timeframe
        self._short = short_period
        self._long = long_period
        self._low = low_ratio
        self._high = high_ratio

    def _neutral(self, reason: str, score: float = 0.0) -> SkillResult:
        return SkillResult(
            skill_name=self.name,
            direction=Direction.NEUTRAL,
            score=clamp01(score),
            evidence=(reason,),
        )

    def analyze(self, ctx: MarketContext) -> SkillResult:
        candles = ctx.candles(self._tf)
        if len(candles) < self._long + 1:
            return self._neutral(f"insufficient data ({len(candles)} bars)")

        atr_long = atr(candles, self._long)
        if atr_long <= 0:
            return self._neutral("degenerate ATR (flat market)")
        atr_short = atr(candles, self._short)
        ratio = atr_short / atr_long

        if ratio < self._low:
            label = "low volatility (chop)"
            score = clamp01(ratio / self._low) * 0.4
        elif ratio > self._high:
            label = "high volatility (erratic)"
            score = clamp01(self._high / ratio) * 0.6
        else:
            label = "normal volatility"
            score = 0.9

        return SkillResult(
            skill_name=self.name,
            direction=Direction.NEUTRAL,
            score=clamp01(score),
            evidence=(label, f"ATR ratio {ratio:.2f}"),
            meta={"atr_short": atr_short, "atr_long": atr_long, "ratio": ratio},
        )
