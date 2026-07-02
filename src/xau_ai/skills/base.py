"""Base class shared by every analytical skill."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from xau_ai.core.models import MarketContext, SkillResult


class BaseSkill(ABC):
    """Abstract, stateless analyser.

    Subclasses set a unique class-level ``name`` and implement ``analyze``.
    Skills must be independent: no skill may depend on another skill's output.
    """

    name: ClassVar[str] = ""

    @abstractmethod
    def analyze(self, ctx: MarketContext) -> SkillResult:
        """Analyse ``ctx`` and return a directional vote with a confidence score."""
        raise NotImplementedError
