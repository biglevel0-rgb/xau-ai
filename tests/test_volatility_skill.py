"""Tests for the volatility skill."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from xau_ai.core.models import Candle, Direction, MarketContext, Timeframe
from xau_ai.skills.volatility import VolatilitySkill

AS_OF = datetime(2026, 7, 2, 15, 0, 0)


def _vol_candles(spec: list[tuple[float, float]]) -> list[Candle]:
    """Build candles from (price, half_range) rows (open == close == price)."""
    ts = datetime(2026, 7, 2, 8, 0, 0)
    return [
        Candle(
            timestamp=ts + timedelta(minutes=5 * i),
            open=price,
            high=price + wick,
            low=price - wick,
            close=price,
            volume=100.0,
        )
        for i, (price, wick) in enumerate(spec)
    ]


def _ctx(spec: list[tuple[float, float]]) -> MarketContext:
    return MarketContext(symbol="XAUUSD", as_of=AS_OF, series={Timeframe.M5: _vol_candles(spec)})


def test_direction_is_always_neutral() -> None:
    result = VolatilitySkill().analyze(_ctx([(3300.0, 2.0)] * 60))
    assert result.direction is Direction.NEUTRAL


def test_normal_regime_scores_high() -> None:
    result = VolatilitySkill().analyze(_ctx([(3300.0, 2.0)] * 60))
    assert any("normal" in e for e in result.evidence)
    assert result.score == pytest.approx(0.9)


def test_high_volatility_regime() -> None:
    spec = [(3300.0, 1.0)] * 46 + [(3300.0, 10.0)] * 14  # recent bars far wider
    result = VolatilitySkill().analyze(_ctx(spec))
    assert any("high volatility" in e for e in result.evidence)


def test_low_volatility_regime() -> None:
    spec = [(3300.0, 10.0)] * 46 + [(3300.0, 1.0)] * 14  # recent bars far calmer
    result = VolatilitySkill().analyze(_ctx(spec))
    assert any("low volatility" in e for e in result.evidence)


def test_insufficient_data_is_neutral() -> None:
    result = VolatilitySkill().analyze(_ctx([(3300.0, 2.0)] * 10))
    assert "insufficient" in result.evidence[0]


def test_degenerate_atr_is_neutral() -> None:
    result = VolatilitySkill().analyze(_ctx([(3300.0, 0.0)] * 60))
    assert "degenerate" in result.evidence[0]


def test_short_must_be_shorter_than_long() -> None:
    with pytest.raises(ValueError, match="shorter"):
        VolatilitySkill(short_period=50, long_period=14)


def test_skill_is_registered() -> None:
    from xau_ai.core.registry import registry

    assert registry.get("volatility") is VolatilitySkill
