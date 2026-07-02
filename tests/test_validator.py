"""Tests for the validator."""

from __future__ import annotations

from xau_ai.config.settings import ValidatorConfig
from xau_ai.core.models import Direction, SkillResult
from xau_ai.validator.validator import Validator

WEIGHTS = {"trend": 0.5, "market_structure": 0.5}


def _validator() -> Validator:
    return Validator(ValidatorConfig(confidence_threshold=0.85, weights=WEIGHTS))


def _result(name: str, direction: Direction, score: float) -> SkillResult:
    return SkillResult(skill_name=name, direction=direction, score=score)


def test_unanimous_long() -> None:
    agg = _validator().aggregate(
        [
            _result("trend", Direction.LONG, 0.8),
            _result("market_structure", Direction.LONG, 0.6),
        ]
    )
    assert agg.direction is Direction.LONG
    assert agg.confidence == 0.7  # 0.5*0.8 + 0.5*0.6
    assert set(agg.agreeing) == {"trend", "market_structure"}
    assert agg.disagreeing == ()


def test_tie_is_neutral() -> None:
    agg = _validator().aggregate(
        [
            _result("trend", Direction.LONG, 0.8),
            _result("market_structure", Direction.SHORT, 0.8),
        ]
    )
    assert agg.direction is Direction.NEUTRAL
    assert agg.confidence == 0.0


def test_neutral_skill_abstains() -> None:
    agg = _validator().aggregate(
        [
            _result("trend", Direction.NEUTRAL, 0.9),
            _result("market_structure", Direction.LONG, 0.6),
        ]
    )
    assert agg.direction is Direction.LONG
    assert agg.confidence == 0.3  # only ms contributes, over total weight 1.0
    assert agg.agreeing == ("market_structure",)


def test_unweighted_skill_ignored() -> None:
    agg = _validator().aggregate(
        [
            _result("trend", Direction.LONG, 0.8),
            _result("market_structure", Direction.LONG, 0.8),
            _result("session", Direction.SHORT, 1.0),  # not in weights
        ]
    )
    assert agg.direction is Direction.LONG
    assert "session" not in agg.contributions


def test_disagreeing_recorded() -> None:
    agg = _validator().aggregate(
        [
            _result("trend", Direction.LONG, 0.9),
            _result("market_structure", Direction.SHORT, 0.4),
        ]
    )
    assert agg.direction is Direction.LONG
    assert agg.disagreeing == ("market_structure",)


def test_no_weighted_results_is_neutral() -> None:
    agg = _validator().aggregate([_result("session", Direction.LONG, 1.0)])
    assert agg.direction is Direction.NEUTRAL
    assert agg.confidence == 0.0
