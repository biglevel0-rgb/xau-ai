"""Tests for the liquidity skill."""

from __future__ import annotations

from datetime import datetime

from xau_ai.core.models import Direction, MarketContext, Timeframe
from xau_ai.skills.liquidity import LiquiditySkill

from .conftest import candles_from_prices, ohlc_candles

AS_OF = datetime(2026, 7, 2, 15, 0, 0)

OHLC = tuple[float, float, float, float]


def _ctx(rows: list[OHLC]) -> MarketContext:
    return MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: ohlc_candles(rows)},
    )


def _skill() -> LiquiditySkill:
    return LiquiditySkill(atr_period=3, swing_strength=1)


def test_bearish_sweep_is_short() -> None:
    rows: list[OHLC] = [
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3304.0, 3306.0, 3303.0, 3305.0),  # swing high 3306 (BSL)
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3299.0, 3300.0, 3297.0, 3298.0),
        (3297.0, 3298.0, 3295.0, 3296.0),
        (3300.0, 3308.0, 3299.0, 3301.0),  # wick above 3306, closes back below
    ]
    result = _skill().analyze(_ctx(rows))
    assert result.direction is Direction.SHORT
    assert any("sweep" in e for e in result.evidence)
    assert result.invalidation is not None


def test_bullish_sweep_is_long() -> None:
    rows: list[OHLC] = [
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3296.0, 3297.0, 3294.0, 3295.0),  # swing low 3294 (SSL)
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3301.0, 3303.0, 3300.0, 3302.0),
        (3303.0, 3305.0, 3302.0, 3304.0),
        (3300.0, 3301.0, 3292.0, 3299.0),  # wick below 3294, closes back above
    ]
    result = _skill().analyze(_ctx(rows))
    assert result.direction is Direction.LONG
    assert any("sweep" in e for e in result.evidence)


def test_equal_highs_is_resting_liquidity() -> None:
    rows: list[OHLC] = [
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3304.0, 3306.0, 3303.0, 3305.0),  # swing high 3306
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3304.0, 3306.05, 3303.0, 3305.0),  # swing high 3306.05 ~ equal
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3300.0),
    ]
    result = _skill().analyze(_ctx(rows))
    assert result.direction is Direction.NEUTRAL
    assert any("Equal highs" in e for e in result.evidence)


def test_equal_lows_is_resting_liquidity() -> None:
    rows: list[OHLC] = [
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3296.0, 3297.0, 3294.0, 3295.0),  # swing low 3294
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3296.0, 3297.0, 3294.05, 3295.0),  # swing low 3294.05 ~ equal
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3300.0),
    ]
    result = _skill().analyze(_ctx(rows))
    assert result.direction is Direction.NEUTRAL
    assert any("Equal lows" in e for e in result.evidence)


def test_no_liquidity_event_is_neutral() -> None:
    rows: list[OHLC] = [
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3305.0, 3307.0, 3304.0, 3306.0),  # high 3307
        (3300.0, 3301.0, 3299.0, 3300.0),  # low 3299
        (3310.0, 3312.0, 3309.0, 3311.0),  # high 3312 (distinct)
        (3301.0, 3302.0, 3300.0, 3301.0),  # low 3300 (distinct from 3299)
        (3308.0, 3309.0, 3307.0, 3308.0),  # no sweep, no equal levels
    ]
    result = _skill().analyze(_ctx(rows))
    assert result.direction is Direction.NEUTRAL
    assert "no liquidity event" in result.evidence[0]


def test_no_swings_is_neutral() -> None:
    ctx = MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: candles_from_prices([3300.0] * 6)},
    )
    result = _skill().analyze(ctx)
    assert result.direction is Direction.NEUTRAL
    assert "no swings" in result.evidence[0]


def test_insufficient_data_is_neutral() -> None:
    result = _skill().analyze(_ctx([(3300.0, 3301.0, 3299.0, 3300.0)] * 3))
    assert result.direction is Direction.NEUTRAL
    assert "insufficient" in result.evidence[0]


def test_skill_is_registered() -> None:
    from xau_ai.core.registry import registry

    assert registry.get("liquidity") is LiquiditySkill
