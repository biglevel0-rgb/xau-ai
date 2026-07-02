"""Build a :class:`MarketContext` from a data provider.

This is the seam between the data layer and the skills: it fetches one candle
series per requested timeframe (plus any correlated instruments) and assembles
the immutable context that every skill consumes.

Loading is best-effort: a timeframe or related symbol that is unavailable is
skipped rather than aborting the whole build, but at least one primary series
must load.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    related: Mapping[str, Timeframe] | None = None,
) -> MarketContext:
    """Assemble a :class:`MarketContext` for ``symbol`` across ``timeframes``.

    Fetches ``count`` candles per timeframe. ``related`` maps a correlated symbol
    (e.g. ``"DXY"``) to the timeframe to load it at; correlated series are
    supplementary, so a missing one is skipped silently. ``as_of`` defaults to
    the most recent primary candle timestamp (deterministic; no wall clock).
    """
    if not timeframes:
        raise DataProviderError("at least one timeframe is required")

    series: dict[Timeframe, list[Candle]] = {}
    for timeframe in timeframes:
        candles = _try_load(provider, symbol, timeframe, count)
        if candles:
            series[timeframe] = candles

    if not series:
        raise DataProviderError(f"no candles returned for {symbol}")

    related_series: dict[str, list[Candle]] = {}
    if related:
        for rel_symbol, rel_timeframe in related.items():
            candles = _try_load(provider, rel_symbol, rel_timeframe, count)
            if candles:
                related_series[rel_symbol] = candles

    resolved_as_of = as_of or max(candles[-1].timestamp for candles in series.values())
    return MarketContext(
        symbol=symbol,
        as_of=resolved_as_of,
        series=series,
        related=related_series,
    )


def _try_load(
    provider: DataProvider, symbol: str, timeframe: Timeframe, count: int
) -> list[Candle]:
    """Load candles, returning an empty list if the source is unavailable."""
    try:
        return provider.get_candles(symbol, timeframe, count)
    except DataProviderError:
        return []
