"""Tests for the market-structure skill."""

from __future__ import annotations

from datetime import datetime

from xau_ai.core.models import Direction, MarketContext, Timeframe
from xau_ai.skills.market_structure import MarketStructureSkill

from .conftest import candles_from_prices

AS_OF = datetime(2026, 7, 2, 15, 0, 0)

# Rising zigzag: higher highs (3308, 3320, 3332) and higher lows (3303, 3315).
_UPTREND = [
    3300.0, 3304.0, 3308.0, 3305.0, 3303.0,
    3312.0, 3316.0, 3320.0, 3317.0, 3315.0,
    3324.0, 3328.0, 3332.0, 3329.0, 3327.0,
]


def _ctx(prices: list[float]) -> MarketContext:
    return MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: candles_from_prices(prices)},
    )


def test_bullish_bos_on_uptrend_break() -> None:
    result = MarketStructureSkill().analyze(_ctx([*_UPTREND, 3340.0]))
    assert result.direction is Direction.LONG
    assert "Bullish BOS" in result.evidence
    assert result.score > 0.5
    assert result.invalidation is not None


def test_bearish_bos_on_downtrend_break() -> None:
    downtrend = [2 * 3316.0 - p for p in _UPTREND]  # mirror around 3316
    result = MarketStructureSkill().analyze(_ctx([*downtrend, 3292.0]))
    assert result.direction is Direction.SHORT
    assert "Bearish BOS" in result.evidence


def test_uptrend_without_break_is_weak_long_bias() -> None:
    result = MarketStructureSkill().analyze(_ctx(_UPTREND))
    assert result.direction is Direction.LONG
    assert any("bias" in e for e in result.evidence)
    assert result.score <= 0.4


def test_bearish_choch_when_uptrend_breaks_down() -> None:
    # Uptrend, then price closes below the last higher-low -> change of character.
    result = MarketStructureSkill().analyze(_ctx([*_UPTREND, 3305.0]))
    assert result.direction is Direction.SHORT
    assert "Bearish CHoCH" in result.evidence


def test_bullish_choch_when_downtrend_breaks_up() -> None:
    downtrend = [2 * 3316.0 - p for p in _UPTREND]  # mirror around 3316
    result = MarketStructureSkill().analyze(_ctx([*downtrend, 3327.0]))
    assert result.direction is Direction.LONG
    assert "Bullish CHoCH" in result.evidence


def test_downtrend_without_break_is_weak_short_bias() -> None:
    downtrend = [2 * 3316.0 - p for p in _UPTREND]
    result = MarketStructureSkill().analyze(_ctx(downtrend))
    assert result.direction is Direction.SHORT
    assert any("bias" in e for e in result.evidence)


def test_expanding_range_is_neutral() -> None:
    # Broadening: higher high (3327 > 3318) with lower low (3304 < 3309).
    prices = [
        3310.0, 3314.0, 3318.0, 3313.0, 3309.0,
        3315.0, 3321.0, 3327.0, 3320.0, 3316.0,
        3312.0, 3308.0, 3304.0, 3308.0, 3312.0,
    ]
    result = MarketStructureSkill().analyze(_ctx(prices))
    assert result.direction is Direction.NEUTRAL
    assert "no clear structure" in result.evidence[0]


def test_insufficient_data_is_neutral() -> None:
    result = MarketStructureSkill().analyze(_ctx([3300.0, 3301.0, 3302.0]))
    assert result.direction is Direction.NEUTRAL
    assert "insufficient" in result.evidence[0]


def test_no_swings_is_neutral() -> None:
    result = MarketStructureSkill().analyze(_ctx([3300.0 + i for i in range(20)]))
    assert result.direction is Direction.NEUTRAL
    assert "not enough swings" in result.evidence[0]


def test_skill_is_registered() -> None:
    from xau_ai.core.registry import registry

    assert registry.get("market_structure") is MarketStructureSkill
