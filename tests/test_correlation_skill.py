"""Tests for the correlation skill."""

from __future__ import annotations

from datetime import datetime

from xau_ai.core.models import Direction, MarketContext, Timeframe
from xau_ai.skills.correlation import CorrelationSkill
from xau_ai.skills.correlation.skill import Relationship

from .conftest import candles_from_prices

AS_OF = datetime(2026, 7, 2, 15, 0, 0)


def _ctx(gold: list[float], ref: dict[str, list[float]]) -> MarketContext:
    return MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: candles_from_prices(gold)},
        related={name: candles_from_prices(prices) for name, prices in ref.items()},
    )


def test_inverse_dxy_rising_is_short() -> None:
    # Gold falling while DXY rising -> strong negative correlation -> SHORT.
    gold = [3360.0 - i for i in range(40)]
    dxy = [100.0 + i * 0.1 for i in range(40)]
    result = CorrelationSkill(reference="DXY").analyze(_ctx(gold, {"DXY": dxy}))
    assert result.direction is Direction.SHORT
    assert "DXY" in result.evidence[0]


def test_inverse_dxy_falling_is_long() -> None:
    gold = [3300.0 + i for i in range(40)]
    dxy = [110.0 - i * 0.1 for i in range(40)]
    result = CorrelationSkill(reference="DXY").analyze(_ctx(gold, {"DXY": dxy}))
    assert result.direction is Direction.LONG


def test_positive_silver_rising_is_long() -> None:
    gold = [3300.0 + i for i in range(40)]
    silver = [30.0 + i * 0.05 for i in range(40)]
    result = CorrelationSkill(reference="XAGUSD", relationship=Relationship.POSITIVE).analyze(
        _ctx(gold, {"XAGUSD": silver})
    )
    assert result.direction is Direction.LONG


def test_weak_correlation_is_neutral() -> None:
    gold = [3300.0 + i for i in range(40)]  # trending
    ref = [100.0] * 40  # flat -> zero correlation
    result = CorrelationSkill(reference="DXY").analyze(_ctx(gold, {"DXY": ref}))
    assert result.direction is Direction.NEUTRAL
    assert "weak correlation" in result.evidence[0]


def test_missing_reference_is_neutral() -> None:
    result = CorrelationSkill(reference="DXY").analyze(_ctx([3300.0 + i for i in range(40)], {}))
    assert result.direction is Direction.NEUTRAL
    assert "insufficient" in result.evidence[0]


def test_skill_is_registered() -> None:
    from xau_ai.core.registry import registry

    assert registry.get("correlation") is CorrelationSkill
