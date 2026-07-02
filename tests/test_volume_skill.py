"""Tests for the volume skill."""

from __future__ import annotations

from datetime import datetime, timedelta

from xau_ai.core.models import Candle, Direction, MarketContext, Timeframe
from xau_ai.skills.volume import VolumeSkill

from .conftest import candles_from_prices

AS_OF = datetime(2026, 7, 2, 15, 0, 0)


def _ctx(prices: list[float]) -> MarketContext:
    return MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: candles_from_prices(prices)},
    )


def test_price_above_vwap_is_long() -> None:
    ctx = _ctx([3300.0 + i for i in range(40)])  # rising -> last close above VWAP
    result = VolumeSkill(atr_period=3).analyze(ctx)
    assert result.direction is Direction.LONG
    assert any("above VWAP" in e for e in result.evidence)


def test_price_below_vwap_is_short() -> None:
    ctx = _ctx([3340.0 - i for i in range(40)])  # falling -> last close below VWAP
    result = VolumeSkill(atr_period=3).analyze(ctx)
    assert result.direction is Direction.SHORT


def test_price_at_vwap_is_neutral() -> None:
    ctx = _ctx([3300.0] * 40)  # flat -> close == VWAP
    result = VolumeSkill(atr_period=3).analyze(ctx)
    assert result.direction is Direction.NEUTRAL


def test_volume_surge_lifts_score() -> None:
    ts = datetime(2026, 7, 2, 8, 0, 0)
    base = [
        Candle(
            timestamp=ts + timedelta(minutes=5 * i),
            open=3300.0 + i,
            high=3301.0 + i,
            low=3299.0 + i,
            close=3300.0 + i,
            volume=100.0,
        )
        for i in range(19)
    ]
    spike = Candle(
        timestamp=ts + timedelta(minutes=5 * 19),
        open=3319.0,
        high=3320.0,
        low=3318.0,
        close=3319.0,
        volume=1000.0,  # 10x surge
    )
    ctx = MarketContext(symbol="XAUUSD", as_of=AS_OF, series={Timeframe.M5: [*base, spike]})
    result = VolumeSkill(atr_period=3).analyze(ctx)
    assert result.direction is Direction.LONG
    assert result.meta["surge"] > 2.0


def test_insufficient_data_is_neutral() -> None:
    result = VolumeSkill(atr_period=14).analyze(_ctx([3300.0, 3301.0, 3302.0]))
    assert result.direction is Direction.NEUTRAL
    assert "insufficient" in result.evidence[0]


def test_zero_volume_is_neutral() -> None:
    ts = datetime(2026, 7, 2, 8, 0, 0)
    candles = [
        Candle(
            timestamp=ts + timedelta(minutes=5 * i),
            open=3300.0,
            high=3301.0,
            low=3299.0,
            close=3300.0,
            volume=0.0,
        )
        for i in range(20)
    ]
    ctx = MarketContext(symbol="XAUUSD", as_of=AS_OF, series={Timeframe.M5: candles})
    result = VolumeSkill(atr_period=3).analyze(ctx)
    assert result.direction is Direction.NEUTRAL
    assert "VWAP" in result.evidence[0]


def test_skill_is_registered() -> None:
    from xau_ai.core.registry import registry

    assert registry.get("volume") is VolumeSkill
