"""Tests for the skill registry."""

from __future__ import annotations

import pytest

from xau_ai.core.exceptions import SkillError
from xau_ai.core.models import Direction, MarketContext, SkillResult
from xau_ai.core.registry import SkillRegistry
from xau_ai.skills.base import BaseSkill


class _AlphaSkill(BaseSkill):
    name = "alpha"

    def analyze(self, ctx: MarketContext) -> SkillResult:
        return SkillResult(skill_name=self.name, direction=Direction.LONG, score=0.6)


class _BetaSkill(BaseSkill):
    name = "beta"

    def analyze(self, ctx: MarketContext) -> SkillResult:
        return SkillResult(skill_name=self.name, direction=Direction.NEUTRAL, score=0.4)


class _NamelessSkill(BaseSkill):
    def analyze(self, ctx: MarketContext) -> SkillResult:  # pragma: no cover
        return SkillResult(skill_name="?", direction=Direction.NEUTRAL, score=0.0)


@pytest.fixture
def fresh_registry() -> SkillRegistry:
    return SkillRegistry()


def test_register_and_get(fresh_registry: SkillRegistry) -> None:
    fresh_registry.register(_AlphaSkill)
    assert fresh_registry.get("alpha") is _AlphaSkill


def test_register_returns_class_for_decorator_use(fresh_registry: SkillRegistry) -> None:
    returned = fresh_registry.register(_AlphaSkill)
    assert returned is _AlphaSkill


def test_duplicate_name_rejected(fresh_registry: SkillRegistry) -> None:
    fresh_registry.register(_AlphaSkill)
    with pytest.raises(SkillError, match="duplicate"):
        fresh_registry.register(_AlphaSkill)


def test_empty_name_rejected(fresh_registry: SkillRegistry) -> None:
    with pytest.raises(SkillError, match="empty"):
        fresh_registry.register(_NamelessSkill)


def test_unknown_skill_raises(fresh_registry: SkillRegistry) -> None:
    with pytest.raises(SkillError, match="unknown"):
        fresh_registry.get("missing")


def test_all_sorted_by_name(fresh_registry: SkillRegistry) -> None:
    fresh_registry.register(_BetaSkill)
    fresh_registry.register(_AlphaSkill)
    assert fresh_registry.names() == ("alpha", "beta")
    assert fresh_registry.all() == (_AlphaSkill, _BetaSkill)


def test_clear(fresh_registry: SkillRegistry) -> None:
    fresh_registry.register(_AlphaSkill)
    fresh_registry.clear()
    assert fresh_registry.names() == ()


def test_skill_analyze_contract(fresh_registry: SkillRegistry) -> None:
    ctx = MarketContext(symbol="XAUUSD", as_of=__import__("datetime").datetime(2026, 7, 2))
    result = _AlphaSkill().analyze(ctx)
    assert result.skill_name == "alpha"
    assert 0.0 <= result.score <= 1.0
