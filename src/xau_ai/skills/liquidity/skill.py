"""Liquidity skill.

Detects the tradeable liquidity event and any resting liquidity:

* **Liquidity sweep** (stop hunt) — the latest candle pierces the most recent
  swing level but closes back inside it: a rejection. Sweeping sell-side (SSL)
  below then closing above = LONG; sweeping buy-side (BSL) above then closing
  below = SHORT. This is the only directional trigger.
* **Equal highs/lows** — resting engineered liquidity; reported as evidence.

Sweep wick size is measured in ATR units.
"""

from __future__ import annotations

from typing import ClassVar

from xau_ai.analysis.indicators import atr, clamp01
from xau_ai.analysis.swings import SwingPoint, find_swings
from xau_ai.core.models import Direction, MarketContext, SkillResult, Timeframe
from xau_ai.core.registry import registry
from xau_ai.skills.base import BaseSkill


@registry.register
class LiquiditySkill(BaseSkill):
    """Detect liquidity sweeps and equal highs/lows on a single timeframe."""

    name: ClassVar[str] = "liquidity"

    def __init__(
        self,
        timeframe: Timeframe = Timeframe.M5,
        atr_period: int = 14,
        swing_strength: int = 2,
        equal_tol_atr: float = 0.1,
    ) -> None:
        self._tf = timeframe
        self._atr_period = atr_period
        self._swing = swing_strength
        self._equal_tol_atr = equal_tol_atr

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
        if not highs and not lows:
            return self._neutral("no swings to define liquidity")

        atr_value = max(atr(candles, self._atr_period), 1e-9)
        last = candles[-1]

        if highs:
            ref_high = highs[-1].price
            if last.high > ref_high and last.close < ref_high:
                wick = (last.high - ref_high) / atr_value
                return self._sweep(
                    Direction.SHORT, "Bearish liquidity sweep (BSL grab)", wick, ref_high, "above"
                )
        if lows:
            ref_low = lows[-1].price
            if last.low < ref_low and last.close > ref_low:
                wick = (ref_low - last.low) / atr_value
                return self._sweep(
                    Direction.LONG, "Bullish liquidity sweep (SSL grab)", wick, ref_low, "below"
                )

        return self._resting(highs, lows, atr_value)

    def _sweep(
        self,
        direction: Direction,
        label: str,
        wick_atr: float,
        level: float,
        side: str,
    ) -> SkillResult:
        score = clamp01(0.5 + wick_atr / 2.0)
        return SkillResult(
            skill_name=self.name,
            direction=direction,
            score=score,
            evidence=(label, f"wick {wick_atr:.2f} ATR"),
            invalidation=f"close {side} {level:.2f}",
            meta={"wick_atr": wick_atr},
        )

    def _resting(
        self,
        highs: list[SwingPoint],
        lows: list[SwingPoint],
        atr_value: float,
    ) -> SkillResult:
        tol = self._equal_tol_atr * atr_value
        evidence: list[str] = []
        if len(highs) >= 2 and abs(highs[-1].price - highs[-2].price) <= tol:
            evidence.append("Equal highs (BSL resting)")
        if len(lows) >= 2 and abs(lows[-1].price - lows[-2].price) <= tol:
            evidence.append("Equal lows (SSL resting)")
        if evidence:
            return SkillResult(
                skill_name=self.name,
                direction=Direction.NEUTRAL,
                score=0.2,
                evidence=tuple(evidence),
            )
        return self._neutral("no liquidity event")
