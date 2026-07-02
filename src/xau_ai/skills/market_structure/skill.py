"""Market-structure skill.

Classifies the swing sequence as up (HH + HL) or down (LH + LL), then checks
whether the latest close breaks structure:

* **BOS** (Break of Structure) — a continuation break in the trend direction.
* **CHoCH** (Change of Character) — the first break against the prevailing trend,
  a potential reversal (weighted more strongly than a plain trend bias).

Break strength is the break distance expressed in ATR units.
"""

from __future__ import annotations

from typing import ClassVar

from xau_ai.analysis.indicators import atr, clamp01
from xau_ai.analysis.swings import SwingPoint, find_swings
from xau_ai.core.models import Direction, MarketContext, SkillResult, Timeframe
from xau_ai.core.registry import registry
from xau_ai.skills.base import BaseSkill


@registry.register
class MarketStructureSkill(BaseSkill):
    """Detect trend structure and structure breaks on a single timeframe."""

    name: ClassVar[str] = "market_structure"

    def __init__(
        self,
        timeframe: Timeframe = Timeframe.M5,
        swing_strength: int = 2,
        atr_period: int = 14,
    ) -> None:
        self._tf = timeframe
        self._swing = swing_strength
        self._atr_period = atr_period

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

        swings = find_swings(candles, self._swing, self._swing)
        highs = [s for s in swings if s.kind == "high"]
        lows = [s for s in swings if s.kind == "low"]
        if len(highs) < 2 or len(lows) < 2:
            return self._neutral("not enough swings to define structure")

        higher_high = highs[-1].price > highs[-2].price
        higher_low = lows[-1].price > lows[-2].price
        uptrend = higher_high and higher_low
        downtrend = (not higher_high) and (not higher_low)

        last_close = candles[-1].close
        last_high = highs[-1].price
        last_low = lows[-1].price
        atr_value = max(atr(candles, self._atr_period), 1e-9)

        return self._classify(
            uptrend=uptrend,
            downtrend=downtrend,
            last_close=last_close,
            last_high=last_high,
            last_low=last_low,
            atr_value=atr_value,
            highs=highs,
            lows=lows,
        )

    def _classify(
        self,
        *,
        uptrend: bool,
        downtrend: bool,
        last_close: float,
        last_high: float,
        last_low: float,
        atr_value: float,
        highs: list[SwingPoint],
        lows: list[SwingPoint],
    ) -> SkillResult:
        struct = "HH-HL uptrend" if uptrend else "LH-LL downtrend" if downtrend else "range"

        if uptrend and last_close > last_high:
            return self._event(
                Direction.LONG,
                "Bullish BOS",
                struct,
                (last_close - last_high) / atr_value,
                last_low,
            )
        if downtrend and last_close < last_low:
            return self._event(
                Direction.SHORT,
                "Bearish BOS",
                struct,
                (last_low - last_close) / atr_value,
                last_high,
            )
        if uptrend and last_close < last_low:
            return self._event(
                Direction.SHORT,
                "Bearish CHoCH",
                struct,
                (last_low - last_close) / atr_value,
                last_high,
            )
        if downtrend and last_close > last_high:
            return self._event(
                Direction.LONG,
                "Bullish CHoCH",
                struct,
                (last_close - last_high) / atr_value,
                last_low,
            )

        # Structure present but no break yet: weak directional bias only.
        if uptrend:
            return self._event(Direction.LONG, "HH-HL bias", struct, 0.3, last_low, raw=True)
        if downtrend:
            return self._event(Direction.SHORT, "LH-LL bias", struct, 0.3, last_high, raw=True)
        return self._neutral(f"{struct}: no clear structure")

    def _event(
        self,
        direction: Direction,
        label: str,
        structure: str,
        strength: float,
        invalidation_level: float,
        *,
        raw: bool = False,
    ) -> SkillResult:
        score = clamp01(strength if raw else 0.5 + strength / 2.0)
        side = "below" if direction is Direction.LONG else "above"
        return SkillResult(
            skill_name=self.name,
            direction=direction,
            score=score,
            evidence=(label, structure),
            invalidation=f"close {side} {invalidation_level:.2f}",
            meta={"strength": strength},
        )
