"""Session skill.

Sessions are a *liquidity-quality* filter, not a directional call, so the
direction is always NEUTRAL. The score reflects how tradeable the current
session is (Overlap > London/NY > Asia > off-hours), boosted inside ICT kill
zones. Hours are treated as UTC.
"""

from __future__ import annotations

from datetime import UTC
from typing import ClassVar

from xau_ai.analysis.indicators import clamp01
from xau_ai.core.models import Direction, MarketContext, SkillResult
from xau_ai.core.registry import registry
from xau_ai.skills.base import BaseSkill


@registry.register
class SessionSkill(BaseSkill):
    """Classify the active trading session and its liquidity quality."""

    name: ClassVar[str] = "session"

    def analyze(self, ctx: MarketContext) -> SkillResult:
        moment = ctx.as_of
        hour = moment.astimezone(UTC).hour if moment.tzinfo is not None else moment.hour

        name, base_score = self._session(hour)
        kill_zone = self._kill_zone(hour)
        score = clamp01(base_score + (0.05 if kill_zone else 0.0))

        evidence = [f"{name} session (UTC hour {hour})"]
        if kill_zone:
            evidence.append("ICT kill zone")

        return SkillResult(
            skill_name=self.name,
            direction=Direction.NEUTRAL,
            score=score,
            evidence=tuple(evidence),
            meta={"hour_utc": float(hour), "kill_zone": 1.0 if kill_zone else 0.0},
        )

    @staticmethod
    def _session(hour: int) -> tuple[str, float]:
        if 12 <= hour < 16:
            return "London/NY Overlap", 0.95
        if 7 <= hour < 16:
            return "London", 0.85
        if 12 <= hour < 21:
            return "New York", 0.85
        if hour >= 22 or hour < 7:
            return "Asia", 0.40
        return "Off-hours", 0.20

    @staticmethod
    def _kill_zone(hour: int) -> bool:
        london_kz = 7 <= hour < 10
        new_york_kz = 12 <= hour < 15
        return london_kz or new_york_kz
