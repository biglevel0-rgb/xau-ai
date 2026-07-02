"""Validator.

Aggregates independent :class:`SkillResult` votes into a single directional
verdict using the configured weights. Each skill contributes ``weight * score``
to its side; the winning side's normalised weight is the confidence. NEUTRAL
skills abstain (contribute nothing), which naturally lowers confidence.

The validator only decides *direction and confidence*. Hard gates (RR, required
confirmations, thresholds) live in the signal generator.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from xau_ai.config.settings import ValidatorConfig
from xau_ai.core.models import Direction, SkillResult


@dataclass(frozen=True, slots=True)
class Aggregate:
    """Outcome of aggregating skill votes."""

    direction: Direction
    confidence: float
    long_weight: float
    short_weight: float
    agreeing: tuple[str, ...] = ()
    disagreeing: tuple[str, ...] = ()
    contributions: dict[str, float] = field(default_factory=dict)


class Validator:
    """Combine weighted skill votes into a direction and confidence."""

    def __init__(self, config: ValidatorConfig) -> None:
        self._weights = config.weights

    def aggregate(self, results: Sequence[SkillResult]) -> Aggregate:
        """Aggregate ``results`` into an :class:`Aggregate`."""
        long_weight = 0.0
        short_weight = 0.0
        total_weight = 0.0
        contributions: dict[str, float] = {}

        for result in results:
            weight = self._weights.get(result.skill_name, 0.0)
            if weight <= 0.0:
                continue
            total_weight += weight
            signed = weight * result.score
            if result.direction is Direction.LONG:
                long_weight += signed
                contributions[result.skill_name] = signed
            elif result.direction is Direction.SHORT:
                short_weight += signed
                contributions[result.skill_name] = -signed
            else:
                contributions[result.skill_name] = 0.0

        if total_weight <= 0.0 or long_weight == short_weight:
            return Aggregate(
                direction=Direction.NEUTRAL,
                confidence=0.0,
                long_weight=long_weight,
                short_weight=short_weight,
                contributions=contributions,
            )

        direction = Direction.LONG if long_weight > short_weight else Direction.SHORT
        confidence = max(long_weight, short_weight) / total_weight
        agreeing = tuple(
            r.skill_name
            for r in results
            if r.direction is direction and self._weights.get(r.skill_name, 0.0) > 0.0
        )
        disagreeing = tuple(
            r.skill_name
            for r in results
            if r.direction is not direction
            and r.direction is not Direction.NEUTRAL
            and self._weights.get(r.skill_name, 0.0) > 0.0
        )
        return Aggregate(
            direction=direction,
            confidence=confidence,
            long_weight=long_weight,
            short_weight=short_weight,
            agreeing=agreeing,
            disagreeing=disagreeing,
            contributions=contributions,
        )
