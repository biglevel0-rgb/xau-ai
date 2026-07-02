"""Tests for the market-context builder."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from xau_ai.core.context import build_context
from xau_ai.core.exceptions import DataProviderError
from xau_ai.core.models import Candle, Timeframe
from xau_ai.data.base import DataProvider

from .conftest import make_candle


class FakeProvider:
    """In-memory provider driven by a per-timeframe candle map."""

    def __init__(self, data: dict[Timeframe, list[Candle]]) -> None:
        self._data = data

    def get_candles(self, symbol: str, timeframe: Timeframe, count: int) -> list[Candle]:
        return self._data.get(timeframe, [])[-count:]


def _series(start: datetime, step_min: int, n: int) -> list[Candle]:
    return [make_candle(start + timedelta(minutes=step_min * i)) for i in range(n)]


def test_fake_provider_satisfies_protocol() -> None:
    assert isinstance(FakeProvider({}), DataProvider)


def test_build_context_collects_timeframes() -> None:
    start = datetime(2026, 7, 2, 15, 0, 0)
    provider = FakeProvider(
        {
            Timeframe.M1: _series(start, 1, 10),
            Timeframe.M5: _series(start, 5, 6),
        }
    )
    ctx = build_context(provider, "XAUUSD", [Timeframe.M1, Timeframe.M5], count=10)
    assert set(ctx.series) == {Timeframe.M1, Timeframe.M5}
    assert len(ctx.candles(Timeframe.M1)) == 10


def test_as_of_defaults_to_latest_timestamp() -> None:
    start = datetime(2026, 7, 2, 15, 0, 0)
    provider = FakeProvider(
        {
            Timeframe.M1: _series(start, 1, 10),  # newest at 15:09
            Timeframe.M5: _series(start, 5, 6),  # newest at 15:25
        }
    )
    ctx = build_context(provider, "XAUUSD", [Timeframe.M1, Timeframe.M5], count=10)
    assert ctx.as_of == datetime(2026, 7, 2, 15, 25, 0)


def test_explicit_as_of_is_respected() -> None:
    start = datetime(2026, 7, 2, 15, 0, 0)
    provider = FakeProvider({Timeframe.M5: _series(start, 5, 3)})
    forced = datetime(2030, 1, 1)
    ctx = build_context(provider, "XAUUSD", [Timeframe.M5], count=5, as_of=forced)
    assert ctx.as_of == forced


def test_empty_timeframes_raises() -> None:
    provider = FakeProvider({})
    with pytest.raises(DataProviderError, match="at least one timeframe"):
        build_context(provider, "XAUUSD", [], count=5)


def test_no_candles_raises() -> None:
    provider = FakeProvider({})
    with pytest.raises(DataProviderError, match="no candles"):
        build_context(provider, "XAUUSD", [Timeframe.M5], count=5)
