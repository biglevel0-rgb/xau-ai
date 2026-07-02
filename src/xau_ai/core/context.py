"""Build a :class:`MarketContext` from a data provider.

This is the seam between the data layer and the skills: it fetches one candle
series per requested timeframe and assembles the immutable context that every
skill consumes.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from xau_ai.core.exceptions import DataProviderError
from xau_ai.core.models import Candle, MarketContext, Timeframe
from xau_ai.data.base import DataProvider


def build_context(
    provider: DataProvider,
    symbol: str,
    timeframes: Sequence[Timeframe],
    count: int,
    as_of: datetime | None = None,
) -> MarketContext:
    """Assemble a :class:`MarketContext` for ``symbol`` across ``timeframes``.

    Fetches ``count`` candles per timeframe. ``as_of`` defaults to the most
    recent candle timestamp across all series (deterministic; no wall clock).
    """
    if not timeframes:
        raise DataProviderError("at least one timeframe is required")

    series: dict[Timeframe, list[Candle]] = {}
    for timeframe in timeframes:
        candles = provider.get_candles(symbol, timeframe, count)
        if candles:
            series[timeframe] = candles

    if not series:
        raise DataProviderError(f"no candles returned for {symbol}")

    resolved_as_of = as_of or max(candles[-1].timestamp for candles in series.values())
    return MarketContext(symbol=symbol, as_of=resolved_as_of, series=series)
