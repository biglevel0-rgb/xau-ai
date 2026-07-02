"""Multi-timeframe confirmation skill.

Computes a simple EMA-based bias on each available timeframe and requires them to
agree. Full agreement across the evaluated timeframes yields a high score; any
conflict yields NEUTRAL. Needs at least two timeframes with enough data — a
single timeframe cannot confirm itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from xau_ai.analysis.indicators import clamp01, ema
from xau_ai.core.models import Candle, Direction, MarketContext, SkillResult, Timeframe
from xau_ai.core.registry import registry
from xau_ai.skills.base import BaseSkill

_DEFAULT_TIMEFRAMES = (Timeframe.M1, Timeframe.M5, Timeframe.M15, Timeframe.H1)


def _bias(candles: Sequence[Candle], fast: int, slow: int) -> Direction:
    """EMA-based directional bias for one timeframe."""
    closes = [c.close for c in candles]
    ema_fast = ema(closes, fast)[-1]
    ema_slow = ema(closes, slow)[-1]
    last = closes[-1]
    if ema_fast > ema_slow and last > ema_slow:
        return Direction.LONG
    if ema_fast < ema_slow and last < ema_slow:
        return Direction.SHORT
    return Direction.NEUTRAL


@registry.register
class MtfConfirmationSkill(BaseSkill):
    """Require trend agreement across multiple timeframes."""

    name: ClassVar[str] = "mtf"

    def __init__(
        self,
        timeframes: Sequence[Timeframe] = _DEFAULT_TIMEFRAMES,
        fast: int = 20,
        slow: int = 50,
    ) -> None:
        if fast >= slow:
            raise ValueError("fast period must be shorter than slow period")
        self._timeframes = tuple(timeframes)
        self._fast = fast
        self._slow = slow

    def _neutral(self, reason: str, score: float = 0.0) -> SkillResult:
        return SkillResult(
            skill_name=self.name,
            direction=Direction.NEUTRAL,
            score=clamp01(score),
            evidence=(reason,),
        )

    def analyze(self, ctx: MarketContext) -> SkillResult:
        votes: dict[Timeframe, Direction] = {}
        for timeframe in self._timeframes:
            candles = ctx.candles(timeframe)
            if len(candles) >= self._slow + 1:
                votes[timeframe] = _bias(candles, self._fast, self._slow)

        if len(votes) < 2:
            return self._neutral("need at least two timeframes with data")

        longs = sum(1 for d in votes.values() if d is Direction.LONG)
        shorts = sum(1 for d in votes.values() if d is Direction.SHORT)
        evidence = tuple(f"{tf.value}:{d.value}" for tf, d in votes.items())

        if longs > 0 and shorts == 0:
            return self._aligned(Direction.LONG, longs, len(votes), evidence)
        if shorts > 0 and longs == 0:
            return self._aligned(Direction.SHORT, shorts, len(votes), evidence)
        return SkillResult(
            skill_name=self.name,
            direction=Direction.NEUTRAL,
            score=0.1,
            evidence=("timeframes conflict", *evidence),
        )

    def _aligned(
        self, direction: Direction, aligned: int, total: int, evidence: tuple[str, ...]
    ) -> SkillResult:
        return SkillResult(
            skill_name=self.name,
            direction=direction,
            score=clamp01(aligned / total),
            evidence=evidence,
            meta={"aligned": float(aligned), "timeframes": float(total)},
        )
