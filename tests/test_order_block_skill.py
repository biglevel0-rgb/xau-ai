"""Tests for the order-block skill."""

from __future__ import annotations

from datetime import datetime

from xau_ai.core.models import Direction, MarketContext, Timeframe
from xau_ai.skills.order_blocks import OrderBlockSkill

from .conftest import ohlc_candles

AS_OF = datetime(2026, 7, 2, 15, 0, 0)

OHLC = tuple[float, float, float, float]


def _ctx(rows: list[OHLC]) -> MarketContext:
    return MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: ohlc_candles(rows)},
    )


def test_bullish_order_block_on_return_to_zone() -> None:
    rows: list[OHLC] = [
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3301.0, 3301.0, 3296.0, 3297.0),  # bearish OB origin (zone 3296-3301)
        (3297.0, 3307.0, 3297.0, 3306.0),  # displacement up
        (3306.0, 3316.0, 3305.0, 3315.0),
        (3315.0, 3317.0, 3308.0, 3309.0),  # pullback
        (3309.0, 3310.0, 3302.0, 3303.0),
        (3303.0, 3304.0, 3300.0, 3301.0),  # back at OB top
    ]
    result = OrderBlockSkill(atr_period=3).analyze(_ctx(rows))
    assert result.direction is Direction.LONG
    assert "Bullish Order Block" in result.evidence
    assert result.score > 0.5
    assert result.invalidation is not None


def test_bearish_order_block() -> None:
    rows: list[OHLC] = [
        (3320.0, 3321.0, 3319.0, 3320.0),
        (3320.0, 3321.0, 3319.0, 3320.0),
        (3320.0, 3321.0, 3319.0, 3320.0),
        (3319.0, 3324.0, 3319.0, 3323.0),  # bullish OB origin (zone 3319-3324)
        (3323.0, 3323.0, 3313.0, 3314.0),  # displacement down
        (3314.0, 3315.0, 3305.0, 3306.0),
        (3306.0, 3312.0, 3304.0, 3311.0),  # pullback up
        (3311.0, 3320.0, 3310.0, 3319.0),  # back at OB
    ]
    result = OrderBlockSkill(atr_period=3).analyze(_ctx(rows))
    assert result.direction is Direction.SHORT
    assert "Bearish Order Block" in result.evidence


def test_price_far_from_block_lowers_proximity() -> None:
    # Price stays at the impulse top, far above the OB zone -> proximity < 1.
    rows: list[OHLC] = [
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3301.0, 3301.0, 3296.0, 3297.0),  # bullish OB (zone 3296-3301)
        (3297.0, 3307.0, 3297.0, 3306.0),
        (3306.0, 3316.0, 3305.0, 3315.0),
        (3315.0, 3320.0, 3314.0, 3319.0),
        (3319.0, 3324.0, 3318.0, 3323.0),  # price far above the block
    ]
    result = OrderBlockSkill(atr_period=3).analyze(_ctx(rows))
    assert result.direction is Direction.LONG
    assert result.meta["proximity"] < 1.0


def test_no_order_block_is_neutral() -> None:
    rows: list[OHLC] = [(3300.0, 3301.0, 3299.0, 3300.0)] * 8  # dojis, no impulse
    result = OrderBlockSkill(atr_period=3).analyze(_ctx(rows))
    assert result.direction is Direction.NEUTRAL
    assert "no qualifying order block" in result.evidence[0]


def test_insufficient_data_is_neutral() -> None:
    rows: list[OHLC] = [(3300.0, 3301.0, 3299.0, 3300.0)] * 3
    result = OrderBlockSkill(atr_period=3).analyze(_ctx(rows))
    assert result.direction is Direction.NEUTRAL
    assert "insufficient" in result.evidence[0]


def test_skill_is_registered() -> None:
    from xau_ai.core.registry import registry

    assert registry.get("order_block") is OrderBlockSkill
