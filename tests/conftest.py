"""Shared test fixtures."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from xau_ai.core.models import Candle, MarketContext, Timeframe


def make_candle(
    ts: datetime,
    open_: float = 3350.0,
    high: float = 3352.0,
    low: float = 3349.0,
    close: float = 3351.0,
    volume: float = 100.0,
) -> Candle:
    """Build a valid candle with sensible gold-priced defaults."""
    return Candle(
        timestamp=ts,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


@pytest.fixture
def sample_candles() -> list[Candle]:
    """Five consecutive M5 candles."""
    start = datetime(2026, 7, 2, 15, 0, 0)
    return [make_candle(start + timedelta(minutes=5 * i)) for i in range(5)]


@pytest.fixture
def sample_context(sample_candles: list[Candle]) -> MarketContext:
    """A market context holding the sample M5 series."""
    return MarketContext(
        symbol="XAUUSD",
        as_of=datetime(2026, 7, 2, 15, 25, 0),
        series={Timeframe.M5: sample_candles},
    )
