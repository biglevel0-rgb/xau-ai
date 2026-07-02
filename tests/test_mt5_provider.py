"""Tests for the MT5 provider.

The ``MetaTrader5`` package is Windows-only and not installed here, so we test:
  * the pure row-conversion helper with fake rows;
  * that a missing package surfaces as ``DataProviderError`` (not ImportError);
  * the timeframe mapping covers every ``Timeframe``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from xau_ai.core.exceptions import DataProviderError
from xau_ai.core.models import Timeframe
from xau_ai.data import mt5_provider
from xau_ai.data.mt5_provider import _TF_ATTR, Mt5DataProvider, _rows_to_candles


class FakeMt5:
    """Minimal stand-in for the MetaTrader5 module."""

    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 16385
    TIMEFRAME_H4 = 16388

    def __init__(self, *, init_ok: bool = True, rates: Any = None) -> None:
        self._init_ok = init_ok
        self._rates = rates
        self.init_kwargs: dict[str, Any] | None = None
        self.shutdown_called = False

    def initialize(self, **kwargs: Any) -> bool:
        self.init_kwargs = kwargs
        return self._init_ok

    def last_error(self) -> tuple[int, str]:
        return (-1, "fake error")

    def copy_rates_from_pos(self, symbol: str, tf: int, start: int, count: int) -> Any:
        return self._rates

    def shutdown(self) -> None:
        self.shutdown_called = True


def _fake_rows() -> list[dict[str, Any]]:
    epoch = int(datetime(2026, 7, 2, 15, 0, tzinfo=UTC).timestamp())
    return [
        {"time": epoch, "open": 3350.0, "high": 3352.0, "low": 3349.0,
         "close": 3351.0, "tick_volume": 100},
        {"time": epoch + 300, "open": 3351.0, "high": 3353.0, "low": 3350.0,
         "close": 3352.0, "tick_volume": 120},
    ]


def test_rows_to_candles_converts_fields() -> None:
    epoch = int(datetime(2026, 7, 2, 15, 0, tzinfo=UTC).timestamp())
    rows = [
        {"time": epoch, "open": 3350.0, "high": 3352.0, "low": 3349.0,
         "close": 3351.0, "tick_volume": 120},
    ]
    candles = _rows_to_candles(rows)
    assert len(candles) == 1
    candle = candles[0]
    assert candle.close == 3351.0
    assert candle.volume == 120.0
    assert candle.timestamp == datetime(2026, 7, 2, 15, 0, tzinfo=UTC)


def test_rows_to_candles_empty() -> None:
    assert _rows_to_candles([]) == []


def test_tf_map_covers_all_timeframes() -> None:
    assert set(_TF_ATTR) == set(Timeframe)


def test_missing_package_raises_data_error() -> None:
    provider = Mt5DataProvider()
    with pytest.raises(DataProviderError, match="MetaTrader5 is not installed"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=5)


def test_non_positive_count_raises() -> None:
    provider = Mt5DataProvider()
    with pytest.raises(DataProviderError, match="positive"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=0)


def test_close_without_connection_is_safe() -> None:
    Mt5DataProvider().close()  # must not raise


def test_get_candles_success_with_fake_module(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeMt5(rates=_fake_rows())
    monkeypatch.setattr(mt5_provider, "_load_mt5", lambda: fake)
    provider = Mt5DataProvider()
    candles = provider.get_candles("XAUUSD", Timeframe.M5, count=2)
    assert [c.close for c in candles] == [3351.0, 3352.0]


def test_credentials_passed_to_initialize(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeMt5(rates=_fake_rows())
    monkeypatch.setattr(mt5_provider, "_load_mt5", lambda: fake)
    provider = Mt5DataProvider(login=123, password="pw", server="Broker-Demo")
    provider.get_candles("XAUUSD", Timeframe.M1, count=1)
    assert fake.init_kwargs == {"login": 123, "password": "pw", "server": "Broker-Demo"}


def test_connection_is_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def _loader() -> FakeMt5:
        nonlocal calls
        calls += 1
        return FakeMt5(rates=_fake_rows())

    monkeypatch.setattr(mt5_provider, "_load_mt5", _loader)
    provider = Mt5DataProvider()
    provider.get_candles("XAUUSD", Timeframe.M5, count=1)
    provider.get_candles("XAUUSD", Timeframe.M5, count=1)
    assert calls == 1  # loaded once, then cached


def test_initialize_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mt5_provider, "_load_mt5", lambda: FakeMt5(init_ok=False))
    provider = Mt5DataProvider()
    with pytest.raises(DataProviderError, match="initialize failed"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=1)


def test_no_rates_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mt5_provider, "_load_mt5", lambda: FakeMt5(rates=None))
    provider = Mt5DataProvider()
    with pytest.raises(DataProviderError, match="no MT5 data"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=1)


def test_empty_rates_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mt5_provider, "_load_mt5", lambda: FakeMt5(rates=[]))
    provider = Mt5DataProvider()
    with pytest.raises(DataProviderError, match="no MT5 data"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=1)


def test_close_shuts_down_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeMt5(rates=_fake_rows())
    monkeypatch.setattr(mt5_provider, "_load_mt5", lambda: fake)
    provider = Mt5DataProvider()
    provider.get_candles("XAUUSD", Timeframe.M5, count=1)
    provider.close()
    assert fake.shutdown_called is True
