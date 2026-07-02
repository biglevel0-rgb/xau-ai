"""Data-provider abstraction.

A ``DataProvider`` returns OHLCV candles for a symbol/timeframe. Concrete
implementations (CSV for tests/backtest, MT5 for local dev, cloud APIs for prod)
are interchangeable behind this Protocol.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from xau_ai.core.models import Candle, Timeframe


@runtime_checkable
class DataProvider(Protocol):
    """Source of OHLCV candles."""

    def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int,
    ) -> list[Candle]:
        """Return up to ``count`` most recent candles, oldest -> newest."""
        ...
