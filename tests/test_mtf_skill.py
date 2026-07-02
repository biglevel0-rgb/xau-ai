"""Tests for the multi-timeframe confirmation skill."""

from __future__ import annotations

from datetime import datetime

import pytest

from xau_ai.core.models import Candle, Direction, MarketContext, Timeframe
from xau_ai.skills.mtf import MtfConfirmationSkill

from .conftest import candles_from_prices

AS_OF = datetime(2026, 7, 2, 15, 0, 0)


def _rising() -> list[Candle]:
    return candles_from_prices([3300.0 + i * 2 for i in range(60)])


def _falling() -> list[Candle]:
    return candles_from_prices([3420.0 - i * 2 for i in range(60)])


def test_all_timeframes_up_is_long() -> None:
    ctx = MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: _rising(), Timeframe.H1: _rising()},
    )
    result = MtfConfirmationSkill().analyze(ctx)
    assert result.direction is Direction.LONG
    assert result.score == pytest.approx(1.0)


def test_all_timeframes_down_is_short() -> None:
    ctx = MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: _falling(), Timeframe.H1: _falling()},
    )
    result = MtfConfirmationSkill().analyze(ctx)
    assert result.direction is Direction.SHORT


def test_conflicting_timeframes_is_neutral() -> None:
    ctx = MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: _rising(), Timeframe.H1: _falling()},
    )
    result = MtfConfirmationSkill().analyze(ctx)
    assert result.direction is Direction.NEUTRAL
    assert any("conflict" in e for e in result.evidence)


def test_single_timeframe_cannot_confirm() -> None:
    ctx = MarketContext(symbol="XAUUSD", as_of=AS_OF, series={Timeframe.M5: _rising()})
    result = MtfConfirmationSkill().analyze(ctx)
    assert result.direction is Direction.NEUTRAL
    assert "two timeframes" in result.evidence[0]


def test_insufficient_data_on_all_is_neutral() -> None:
    short = candles_from_prices([3300.0 + i for i in range(10)])
    ctx = MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: short, Timeframe.H1: short},
    )
    result = MtfConfirmationSkill().analyze(ctx)
    assert result.direction is Direction.NEUTRAL


def test_fast_must_be_shorter_than_slow() -> None:
    with pytest.raises(ValueError, match="shorter"):
        MtfConfirmationSkill(fast=50, slow=20)


def test_skill_is_registered() -> None:
    from xau_ai.core.registry import registry

    assert registry.get("mtf") is MtfConfirmationSkill
