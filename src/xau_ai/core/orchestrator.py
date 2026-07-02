"""Orchestrator.

Wires the whole pipeline: instantiate every registered skill, run each against
the market context, and feed the results to the signal generator.

Importing this module imports :mod:`xau_ai.skills`, which registers all built-in
skills with the global registry.
"""

from __future__ import annotations

import xau_ai.skills  # noqa: F401  (import side effect: registers built-in skills)
from xau_ai.config.settings import Settings
from xau_ai.core.models import MarketContext, Signal, SkillResult, Timeframe
from xau_ai.core.registry import registry
from xau_ai.signal.generator import SignalGenerator
from xau_ai.skills.base import BaseSkill


class Orchestrator:
    """Run all registered skills and produce a single signal."""

    def __init__(self, settings: Settings, timeframe: Timeframe = Timeframe.M5) -> None:
        self._settings = settings
        self._skills: list[BaseSkill] = [skill_cls() for skill_cls in registry.all()]
        self._generator = SignalGenerator(settings, timeframe)

    @property
    def skill_names(self) -> tuple[str, ...]:
        """Names of the skills this orchestrator runs."""
        return tuple(type(skill).name for skill in self._skills)

    def run_skills(self, ctx: MarketContext) -> list[SkillResult]:
        """Run every skill independently against ``ctx``."""
        return [skill.analyze(ctx) for skill in self._skills]

    def analyze(self, ctx: MarketContext) -> Signal:
        """Full pipeline: skills -> validator -> signal."""
        results = self.run_skills(ctx)
        return self._generator.generate(ctx, results)
