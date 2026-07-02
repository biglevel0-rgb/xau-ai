"""Tests for core domain models."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from xau_ai.core.models import (
    Candle,
    Direction,
    MarketContext,
    Signal,
    SignalType,
    SkillResult,
    Timeframe,
)

TS = datetime(2026, 7, 2, 15, 0, 0)


class TestCandle:
    def test_valid_candle(self) -> None:
        candle = Candle(timestamp=TS, open=3350, high=3352, low=3349, close=3351, volume=10)
        assert candle.high >= candle.close

    def test_high_below_body_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Candle(timestamp=TS, open=3350, high=3350.5, low=3349, close=3351, volume=10)

    def test_low_above_body_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Candle(timestamp=TS, open=3350, high=3352, low=3350.5, close=3351, volume=10)

    def test_negative_volume_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Candle(timestamp=TS, open=3350, high=3352, low=3349, close=3351, volume=-1)

    def test_candle_is_frozen(self) -> None:
        candle = Candle(timestamp=TS, open=3350, high=3352, low=3349, close=3351, volume=10)
        with pytest.raises(ValidationError):
            candle.close = 9999  # type: ignore[misc]


class TestMarketContext:
    def test_latest_returns_last(self, sample_context: MarketContext) -> None:
        latest = sample_context.latest(Timeframe.M5)
        assert latest is not None
        assert latest.timestamp == datetime(2026, 7, 2, 15, 20, 0)

    def test_latest_missing_timeframe(self, sample_context: MarketContext) -> None:
        assert sample_context.latest(Timeframe.H1) is None

    def test_candles_missing_timeframe_is_empty(self, sample_context: MarketContext) -> None:
        assert sample_context.candles(Timeframe.H4) == []


class TestSkillResult:
    def test_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            SkillResult(skill_name="trend", direction=Direction.LONG, score=1.5)

    def test_valid_result(self) -> None:
        result = SkillResult(
            skill_name="trend",
            direction=Direction.SHORT,
            score=0.8,
            evidence=("CHoCH down",),
        )
        assert result.direction is Direction.SHORT


class TestSignal:
    def test_long_requires_entry_and_stop(self) -> None:
        with pytest.raises(ValidationError):
            Signal(
                signal_type=SignalType.LONG,
                symbol="XAUUSD",
                timeframe=Timeframe.M5,
                as_of=TS,
                confidence=0.9,
            )

    def test_no_trade_must_not_have_entry(self) -> None:
        with pytest.raises(ValidationError):
            Signal(
                signal_type=SignalType.NO_TRADE,
                symbol="XAUUSD",
                timeframe=Timeframe.M5,
                as_of=TS,
                confidence=0.5,
                entry=3350.0,
            )

    def test_entry_equal_stop_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Signal(
                signal_type=SignalType.LONG,
                symbol="XAUUSD",
                timeframe=Timeframe.M5,
                as_of=TS,
                confidence=0.9,
                entry=3350.0,
                stop_loss=3350.0,
            )

    def test_valid_long_signal(self) -> None:
        signal = Signal(
            signal_type=SignalType.LONG,
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            as_of=TS,
            confidence=0.91,
            entry=3352.6,
            stop_loss=3348.9,
            take_profits=(3357.0, 3363.2),
            risk_reward=2.8,
            reasons=("BOS", "Liquidity sweep"),
        )
        assert signal.signal_type is SignalType.LONG
        assert signal.take_profits == (3357.0, 3363.2)

    def test_valid_no_trade_signal(self) -> None:
        signal = Signal(
            signal_type=SignalType.NO_TRADE,
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            as_of=TS,
            confidence=0.78,
            rejections=("FVG not confirmed",),
        )
        assert signal.entry is None
