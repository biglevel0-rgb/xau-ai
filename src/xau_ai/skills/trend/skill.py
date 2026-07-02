"""Trend skill.

Direction comes from the fast/slow EMA relationship; strength is the EMA
separation measured in ATR units, discounted when the fast-EMA slope disagrees
with that direction. Entangled EMAs (separation below a threshold) => NEUTRAL.
"""

from __future__ import annotations

from typing import ClassVar

from xau_ai.analysis.indicators import atr, clamp01, ema
from xau_ai.core.models import Direction, MarketContext, SkillResult, Timeframe
from xau_ai.core.registry import registry
from xau_ai.skills.base import BaseSkill


@registry.register
class TrendSkill(BaseSkill):
    """Classify trend direction and confidence on a single timeframe."""

    name: ClassVar[str] = "trend"

    def __init__(
        self,
        timeframe: Timeframe = Timeframe.M5,
        fast: int = 20,
        slow: int = 50,
        atr_period: int = 14,
        slope_lookback: int = 3,
        flat_threshold: float = 0.1,
    ) -> None:
        if fast >= slow:
            raise ValueError("fast period must be shorter than slow period")
        self._tf = timeframe
        self._fast = fast
        self._slow = slow
        self._atr_period = atr_period
        self._slope_lookback = slope_lookback
        self._flat_threshold = flat_threshold
        self._min_bars = max(slow, atr_period) + slope_lookback + 1

    def _neutral(self, reason: str, score: float = 0.0) -> SkillResult:
        return SkillResult(
            skill_name=self.name,
            direction=Direction.NEUTRAL,
            score=clamp01(score),
            evidence=(reason,),
        )

    def analyze(self, ctx: MarketContext) -> SkillResult:
        candles = ctx.candles(self._tf)
        if len(candles) < self._min_bars:
            return self._neutral(f"insufficient data ({len(candles)}/{self._min_bars} bars)")

        closes = [c.close for c in candles]
        ema_fast = ema(closes, self._fast)
        ema_slow = ema(closes, self._slow)
        atr_value = atr(candles, self._atr_period)
        if atr_value <= 0.0:
            return self._neutral("degenerate ATR (flat market)")

        sep_norm = (ema_fast[-1] - ema_slow[-1]) / atr_value
        slope = ema_fast[-1] - ema_fast[-1 - self._slope_lookback]

        if abs(sep_norm) < self._flat_threshold:
            score = abs(sep_norm) / self._flat_threshold * 0.3
            return self._neutral("EMAs entangled (flat)", score)

        direction = Direction.LONG if sep_norm > 0 else Direction.SHORT
        slope_agrees = (slope > 0) == (sep_norm > 0)
        strength = clamp01(abs(sep_norm) / 2.0)
        score = clamp01(strength * (1.0 if slope_agrees else 0.5))

        relation = f"EMA{self._fast} {'above' if sep_norm > 0 else 'below'} EMA{self._slow}"
        evidence = (
            relation,
            f"separation {sep_norm:+.2f} ATR",
            f"slope {'confirms' if slope_agrees else 'diverges'}",
        )
        return SkillResult(
            skill_name=self.name,
            direction=direction,
            score=score,
            evidence=evidence,
            meta={"separation_atr": sep_norm, "slope": slope},
        )
