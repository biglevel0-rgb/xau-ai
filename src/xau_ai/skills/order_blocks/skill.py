"""Order Block skill.

An order block is the last opposite-colour candle before an impulsive
(displacement) move:

* **Bullish OB** — the last bearish candle before a strong up-move; acts as a
  demand zone. LONG bias.
* **Bearish OB** — the last bullish candle before a strong down-move; a supply
  zone. SHORT bias.

Displacement is measured in ATR units. Confidence blends displacement strength
with how close price currently sits to the block (a return to the zone is the
tradeable event).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from xau_ai.analysis.indicators import atr, clamp01
from xau_ai.core.models import Candle, Direction, MarketContext, SkillResult, Timeframe
from xau_ai.core.registry import registry
from xau_ai.skills.base import BaseSkill


@dataclass(frozen=True, slots=True)
class _OrderBlock:
    index: int
    kind: Literal["bullish", "bearish"]
    top: float
    bottom: float
    displacement: float


@registry.register
class OrderBlockSkill(BaseSkill):
    """Detect the most recent mitigated order block on a single timeframe."""

    name: ClassVar[str] = "order_block"

    def __init__(
        self,
        timeframe: Timeframe = Timeframe.M5,
        atr_period: int = 14,
        impulse: int = 3,
        displacement_atr: float = 1.0,
        proximity_window: float = 3.0,
    ) -> None:
        self._tf = timeframe
        self._atr_period = atr_period
        self._impulse = impulse
        self._displacement_atr = displacement_atr
        self._proximity_window = proximity_window

    def _neutral(self, reason: str, score: float = 0.0) -> SkillResult:
        return SkillResult(
            skill_name=self.name,
            direction=Direction.NEUTRAL,
            score=clamp01(score),
            evidence=(reason,),
        )

    def _find_ob(self, candles: list[Candle], min_displacement: float) -> _OrderBlock | None:
        """Return the strongest qualifying order block (largest displacement).

        Picking by displacement rather than recency keeps a significant
        institutional move from being overridden by minor pullback candles.
        """
        best: _OrderBlock | None = None
        n = len(candles)
        for i in range(n - 1):
            candle = candles[i]
            end = min(i + 1 + self._impulse, n)
            follow = candles[i + 1 : end]
            if not follow:
                continue
            if candle.close < candle.open:  # bearish candle -> potential bullish OB
                displacement = max(c.high for c in follow) - candle.high
                kind: Literal["bullish", "bearish"] = "bullish"
            elif candle.close > candle.open:  # bullish candle -> potential bearish OB
                displacement = candle.low - min(c.low for c in follow)
                kind = "bearish"
            else:
                continue
            if displacement < min_displacement:
                continue
            if best is None or displacement > best.displacement:
                best = _OrderBlock(i, kind, candle.high, candle.low, displacement)
        return best

    def _proximity(self, ob: _OrderBlock, last_close: float, atr_value: float) -> float:
        if ob.bottom <= last_close <= ob.top:
            return 1.0
        distance = ob.bottom - last_close if last_close < ob.bottom else last_close - ob.top
        return clamp01(1.0 - (distance / atr_value) / self._proximity_window)

    def analyze(self, ctx: MarketContext) -> SkillResult:
        candles = ctx.candles(self._tf)
        if len(candles) < self._atr_period + 1:
            return self._neutral(f"insufficient data ({len(candles)} bars)")

        atr_value = max(atr(candles, self._atr_period), 1e-9)
        ob = self._find_ob(candles, self._displacement_atr * atr_value)
        if ob is None:
            return self._neutral("no qualifying order block")

        last_close = candles[-1].close
        proximity = self._proximity(ob, last_close, atr_value)
        strength = clamp01((ob.displacement / atr_value) / 2.0)
        score = clamp01(0.5 * strength + 0.5 * proximity)

        direction = Direction.LONG if ob.kind == "bullish" else Direction.SHORT
        side = "below" if direction is Direction.LONG else "above"
        level = ob.bottom if direction is Direction.LONG else ob.top
        return SkillResult(
            skill_name=self.name,
            direction=direction,
            score=score,
            evidence=(
                f"{ob.kind.capitalize()} Order Block",
                f"displacement {ob.displacement / atr_value:.2f} ATR",
                f"proximity {proximity:.2f}",
            ),
            invalidation=f"close {side} {level:.2f}",
            meta={"displacement_atr": ob.displacement / atr_value, "proximity": proximity},
        )
