"""Tests for the FVG skill."""

from __future__ import annotations

from datetime import datetime

from xau_ai.core.models import Direction, MarketContext, Timeframe
from xau_ai.skills.fvg import FvgSkill

from .conftest import candles_from_prices

AS_OF = datetime(2026, 7, 2, 15, 0, 0)


def _ctx(prices: list[float]) -> MarketContext:
    return MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: candles_from_prices(prices)},
    )


def test_bullish_gap_is_long() -> None:
    prices = [3300.0] * 6 + [3300.0, 3305.0, 3306.0]  # jump creates bullish FVG
    result = FvgSkill(atr_period=3).analyze(_ctx(prices))
    assert result.direction is Direction.LONG
    assert "Bullish FVG" in result.evidence
    assert result.score > 0.5


def test_bearish_gap_is_short() -> None:
    prices = [3306.0] * 6 + [3306.0, 3301.0, 3300.0]  # drop creates bearish FVG
    result = FvgSkill(atr_period=3).analyze(_ctx(prices))
    assert result.direction is Direction.SHORT
    assert "Bearish FVG" in result.evidence


def test_no_gap_is_neutral() -> None:
    result = FvgSkill(atr_period=3).analyze(_ctx([3300.0] * 10))
    assert result.direction is Direction.NEUTRAL
    assert "no FVG" in result.evidence[0]


def test_gap_below_threshold_is_neutral() -> None:
    prices = [3300.0] * 6 + [3300.0, 3305.0, 3306.0]
    result = FvgSkill(atr_period=3, min_size_atr=50.0).analyze(_ctx(prices))
    assert result.direction is Direction.NEUTRAL
    assert "significance" in result.evidence[0]


def test_insufficient_data_is_neutral() -> None:
    result = FvgSkill(atr_period=14).analyze(_ctx([3300.0, 3301.0, 3302.0]))
    assert result.direction is Direction.NEUTRAL
    assert "insufficient" in result.evidence[0]


def test_skill_is_registered() -> None:
    from xau_ai.core.registry import registry

    assert registry.get("fvg") is FvgSkill
