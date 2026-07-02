"""Correlation skill.

Confirms gold's direction against a correlated instrument held in
``ctx.related`` (e.g. DXY, US10Y — inverse; Silver — positive). If the
correlation over the window is strong enough, the reference's trend implies an
expected gold direction; confidence is the absolute correlation.

The reference series is read from the context, so wiring a data source in does
not change this skill.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from xau_ai.analysis.indicators import clamp01, correlation
from xau_ai.core.models import Direction, MarketContext, SkillResult, Timeframe
from xau_ai.core.registry import registry
from xau_ai.skills.base import BaseSkill


class Relationship(StrEnum):
    """How the reference moves relative to gold."""

    INVERSE = "inverse"  # DXY, US10Y
    POSITIVE = "positive"  # Silver, EURUSD (both anti-dollar)


# How well-known references relate to gold. EURUSD is a free-tier proxy for
# (inverse) DXY: dollar weakens -> both EUR and gold rise.
DEFAULT_RELATIONSHIPS: dict[str, Relationship] = {
    "DXY": Relationship.INVERSE,
    "US10Y": Relationship.INVERSE,
    "XAGUSD": Relationship.POSITIVE,
    "EURUSD": Relationship.POSITIVE,
}


@registry.register
class CorrelationSkill(BaseSkill):
    """Confirm gold direction via a correlated instrument."""

    name: ClassVar[str] = "correlation"

    def __init__(
        self,
        reference: str = "DXY",
        relationship: Relationship = Relationship.INVERSE,
        timeframe: Timeframe = Timeframe.M5,
        window: int = 30,
        min_corr: float = 0.3,
    ) -> None:
        self._reference = reference
        self._relationship = relationship
        self._tf = timeframe
        self._window = window
        self._min_corr = min_corr

    def _neutral(self, reason: str, score: float = 0.0) -> SkillResult:
        return SkillResult(
            skill_name=self.name,
            direction=Direction.NEUTRAL,
            score=clamp01(score),
            evidence=(reason,),
        )

    def analyze(self, ctx: MarketContext) -> SkillResult:
        gold = ctx.candles(self._tf)
        reference = ctx.related.get(self._reference, [])
        usable = min(len(gold), len(reference))
        if usable < self._window:
            return self._neutral(f"insufficient {self._reference} data")

        gold_closes = [c.close for c in gold[-self._window :]]
        ref_closes = [c.close for c in reference[-self._window :]]
        corr = correlation(gold_closes, ref_closes)
        if abs(corr) < self._min_corr:
            return self._neutral(f"weak correlation with {self._reference} ({corr:+.2f})")

        ref_up = ref_closes[-1] > ref_closes[0]
        if self._relationship is Relationship.INVERSE:
            direction = Direction.SHORT if ref_up else Direction.LONG
        else:
            direction = Direction.LONG if ref_up else Direction.SHORT

        return SkillResult(
            skill_name=self.name,
            direction=direction,
            score=clamp01(abs(corr)),
            evidence=(
                f"{self._reference} {self._relationship.value}",
                f"correlation {corr:+.2f}",
                f"{self._reference} {'up' if ref_up else 'down'}",
            ),
            meta={"correlation": corr},
        )
