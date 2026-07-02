"""Tests for the trend skill."""

from __future__ import annotations

from datetime import datetime

from xau_ai.core.models import Direction, MarketContext, Timeframe
from xau_ai.skills.trend import TrendSkill

from .conftest import candles_from_prices

AS_OF = datetime(2026, 7, 2, 15, 0, 0)


def _ctx(prices: list[float]) -> MarketContext:
    return MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: candles_from_prices(prices)},
    )


def test_rising_market_is_long() -> None:
    ctx = _ctx([3300.0 + i * 2 for i in range(60)])
    result = TrendSkill().analyze(ctx)
    assert result.direction is Direction.LONG
    assert result.score > 0.5


def test_falling_market_is_short() -> None:
    ctx = _ctx([3300.0 - i * 2 for i in range(60)])
    result = TrendSkill().analyze(ctx)
    assert result.direction is Direction.SHORT
    assert result.score > 0.5


def test_flat_market_is_neutral() -> None:
    ctx = _ctx([3300.0] * 60)
    result = TrendSkill().analyze(ctx)
    assert result.direction is Direction.NEUTRAL
    assert result.score == 0.0


def test_degenerate_atr_is_neutral() -> None:
    candles = candles_from_prices([3300.0] * 60, wick=0.0)  # zero range -> ATR 0
    ctx = MarketContext(symbol="XAUUSD", as_of=AS_OF, series={Timeframe.M5: candles})
    result = TrendSkill().analyze(ctx)
    assert result.direction is Direction.NEUTRAL
    assert "degenerate" in result.evidence[0]


def test_insufficient_data_is_neutral() -> None:
    ctx = _ctx([3300.0 + i for i in range(10)])
    result = TrendSkill().analyze(ctx)
    assert result.direction is Direction.NEUTRAL
    assert "insufficient" in result.evidence[0]


def test_fast_must_be_shorter_than_slow() -> None:
    import pytest

    with pytest.raises(ValueError, match="shorter"):
        TrendSkill(fast=50, slow=20)


def test_skill_is_registered() -> None:
    from xau_ai.core.registry import registry

    assert registry.get("trend") is TrendSkill
