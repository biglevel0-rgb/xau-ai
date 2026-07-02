"""Shared test fixtures."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from xau_ai.config.settings import (
    NewsConfig,
    RiskConfig,
    Settings,
    ValidatorConfig,
)
from xau_ai.core.models import Candle, MarketContext, Timeframe


def make_settings(
    confidence_threshold: float = 0.6,
    required_confirmations: tuple[str, ...] = (),
    min_rr: float = 2.0,
    weights: dict[str, float] | None = None,
) -> Settings:
    """Build a Settings object for tests without touching disk."""
    return Settings(
        symbol="XAUUSD",
        timeframes=(Timeframe.M5,),
        risk=RiskConfig(
            risk_per_trade_pct=0.5,
            min_rr=min_rr,
            max_daily_loss_pct=3.0,
            max_weekly_loss_pct=6.0,
        ),
        validator=ValidatorConfig(
            confidence_threshold=confidence_threshold,
            weights=weights or {"trend": 0.5, "market_structure": 0.5},
            required_confirmations=required_confirmations,
        ),
        news=NewsConfig(block_minutes_before=15, block_minutes_after=15),
    )


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


def candles_from_prices(
    prices: list[float],
    start: datetime | None = None,
    step_min: int = 5,
    wick: float = 1.0,
) -> list[Candle]:
    """Build a candle series from a list of prices.

    Each bar is centred on its price (open == close == price) with symmetric
    ``wick`` high/low, so a bar's high/low track its price directly and swing
    detection stays independent of neighbouring bars.
    """
    origin = start or datetime(2026, 7, 2, 8, 0, 0)
    candles: list[Candle] = []
    for i, price in enumerate(prices):
        candles.append(
            Candle(
                timestamp=origin + timedelta(minutes=step_min * i),
                open=price,
                high=price + wick,
                low=price - wick,
                close=price,
                volume=100.0,
            )
        )
    return candles


def ohlc_candles(
    rows: list[tuple[float, float, float, float]],
    start: datetime | None = None,
    step_min: int = 5,
) -> list[Candle]:
    """Build a candle series from explicit ``(open, high, low, close)`` rows."""
    origin = start or datetime(2026, 7, 2, 8, 0, 0)
    return [
        Candle(
            timestamp=origin + timedelta(minutes=step_min * i),
            open=o,
            high=h,
            low=low,
            close=c,
            volume=100.0,
        )
        for i, (o, h, low, c) in enumerate(rows)
    ]


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
