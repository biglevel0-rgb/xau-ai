"""Tests for the TwelveData provider."""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

import pytest

from xau_ai.core.exceptions import DataProviderError
from xau_ai.core.models import Timeframe
from xau_ai.data.twelvedata import TwelveDataProvider, _http_get_json


def _ok_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "values": [
            {
                "datetime": "2026-07-02 15:00:00",
                "open": "3350",
                "high": "3352",
                "low": "3349",
                "close": "3351",
                "volume": "100",
            },
            {
                "datetime": "2026-07-02 15:05:00",
                "open": "3351",
                "high": "3353",
                "low": "3350",
                "close": "3352",
            },  # no volume (XAU has none)
        ],
    }


class _Capture:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.params: dict[str, str] = {}

    def __call__(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        self.params = params
        return self.payload


def test_requires_api_key() -> None:
    with pytest.raises(DataProviderError, match="API key"):
        TwelveDataProvider("")


def test_parses_candles_oldest_first() -> None:
    provider = TwelveDataProvider("KEY", transport=_Capture(_ok_payload()))
    candles = provider.get_candles("XAUUSD", Timeframe.M5, count=10)
    assert len(candles) == 2
    assert candles[0].close == 3351.0
    assert candles[1].close == 3352.0
    assert candles[1].volume == 0.0  # missing volume -> 0


def test_maps_symbol_and_interval() -> None:
    capture = _Capture(_ok_payload())
    TwelveDataProvider("KEY", transport=capture).get_candles("XAUUSD", Timeframe.M15, count=5)
    assert capture.params["symbol"] == "XAU/USD"
    assert capture.params["interval"] == "15min"
    assert capture.params["apikey"] == "KEY"
    assert capture.params["order"] == "ASC"
    assert capture.params["timezone"] == "UTC"


def test_unmapped_symbol_passes_through() -> None:
    capture = _Capture(_ok_payload())
    TwelveDataProvider("KEY", transport=capture).get_candles("GBPUSD", Timeframe.M5, count=5)
    assert capture.params["symbol"] == "GBPUSD"


def test_count_limits_result() -> None:
    provider = TwelveDataProvider("KEY", transport=_Capture(_ok_payload()))
    candles = provider.get_candles("XAUUSD", Timeframe.M5, count=1)
    assert len(candles) == 1
    assert candles[0].close == 3352.0  # most recent


def test_error_status_raises() -> None:
    payload = {"status": "error", "message": "invalid api key", "code": 401}
    provider = TwelveDataProvider("KEY", transport=_Capture(payload))
    with pytest.raises(DataProviderError, match="invalid api key"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=5)


def test_empty_values_raises() -> None:
    provider = TwelveDataProvider("KEY", transport=_Capture({"status": "ok", "values": []}))
    with pytest.raises(DataProviderError, match="no values"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=5)


def test_bad_row_raises() -> None:
    payload = {
        "status": "ok",
        "values": [
            {"datetime": "2026-07-02 15:00:00", "open": "x", "high": "1", "low": "0", "close": "1"}
        ],
    }
    provider = TwelveDataProvider("KEY", transport=_Capture(payload))
    with pytest.raises(DataProviderError, match="bad row"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=5)


def test_non_positive_count_raises() -> None:
    provider = TwelveDataProvider("KEY", transport=_Capture(_ok_payload()))
    with pytest.raises(DataProviderError, match="positive"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=0)


def test_all_intervals_mapped() -> None:
    from xau_ai.data.twelvedata import _INTERVALS

    assert set(_INTERVALS) == set(Timeframe)


# --- default HTTP transport ---


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_http_get_json_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(200, b'{"status":"ok"}'),
    )
    assert _http_get_json("https://x", {"a": "b"}) == {"status": "ok"}


def test_http_get_json_bad_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: _FakeResponse(500, b""))
    with pytest.raises(DataProviderError, match="HTTP 500"):
        _http_get_json("https://x", {})


def test_http_get_json_urlerror(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(request: Any, timeout: int) -> _FakeResponse:
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    with pytest.raises(DataProviderError, match="failed"):
        _http_get_json("https://x", {})


def test_provider_satisfies_protocol() -> None:
    from xau_ai.data.base import DataProvider

    assert isinstance(TwelveDataProvider("KEY"), DataProvider)


def test_datetime_parsed() -> None:
    provider = TwelveDataProvider("KEY", transport=_Capture(_ok_payload()))
    candles = provider.get_candles("XAUUSD", Timeframe.M5, count=10)
    assert candles[0].timestamp == datetime(2026, 7, 2, 15, 0, 0)
