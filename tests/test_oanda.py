"""Tests for the OANDA provider."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from xau_ai.core.exceptions import DataProviderError
from xau_ai.core.models import Timeframe
from xau_ai.data.oanda import OandaDataProvider


def _payload() -> dict[str, Any]:
    return {
        "candles": [
            {
                "time": "2026-07-03T01:00:00.000000000Z",
                "volume": 120,
                "mid": {"o": "3350.1", "h": "3352.4", "l": "3349.2", "c": "3351.0"},
            },
            {
                "time": "2026-07-03T01:05:00.000000000Z",
                "volume": 90,
                "mid": {"o": "3351.0", "h": "3353.0", "l": "3350.5", "c": "3352.2"},
            },
        ]
    }


class _Capture:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.url = ""
        self.params: dict[str, str] = {}
        self.headers: dict[str, str] = {}

    def __call__(self, url: str, params: dict[str, str], headers: dict[str, str]) -> Any:
        self.url, self.params, self.headers = url, params, headers
        return self.payload


def test_requires_token() -> None:
    with pytest.raises(DataProviderError, match="token"):
        OandaDataProvider("")


def test_unknown_environment_rejected() -> None:
    with pytest.raises(DataProviderError, match="environment"):
        OandaDataProvider("TOKEN", environment="staging")


def test_parses_candles() -> None:
    provider = OandaDataProvider("TOKEN", transport=_Capture(_payload()))
    candles = provider.get_candles("XAUUSD", Timeframe.M5, count=10)
    assert len(candles) == 2
    assert candles[0].close == 3351.0
    assert candles[0].timestamp == datetime(2026, 7, 3, 1, 0, 0)
    assert candles[1].volume == 90.0


def test_symbol_granularity_and_auth() -> None:
    capture = _Capture(_payload())
    OandaDataProvider("TOKEN", transport=capture).get_candles("XAUUSD", Timeframe.M15, count=5)
    assert "/instruments/XAU_USD/candles" in capture.url
    assert "api-fxpractice" in capture.url
    assert capture.params["granularity"] == "M15"
    assert capture.headers["Authorization"] == "Bearer TOKEN"


def test_live_environment_host() -> None:
    capture = _Capture(_payload())
    provider = OandaDataProvider("TOKEN", environment="live", transport=capture)
    provider.get_candles("EURUSD", Timeframe.M1, count=5)
    assert "api-fxtrade" in capture.url
    assert "/instruments/EUR_USD/" in capture.url


def test_error_message_raises() -> None:
    provider = OandaDataProvider(
        "TOKEN", transport=_Capture({"errorMessage": "Insufficient authorization"})
    )
    with pytest.raises(DataProviderError, match="Insufficient authorization"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=5)


def test_empty_candles_raises() -> None:
    provider = OandaDataProvider("TOKEN", transport=_Capture({"candles": []}))
    with pytest.raises(DataProviderError, match="no candles"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=5)


def test_bad_candle_raises() -> None:
    payload = {"candles": [{"time": "2026-07-03T01:00:00.000000000Z", "mid": {"o": "x"}}]}
    provider = OandaDataProvider("TOKEN", transport=_Capture(payload))
    with pytest.raises(DataProviderError, match="bad candle"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=5)


def test_non_positive_count_raises() -> None:
    provider = OandaDataProvider("TOKEN", transport=_Capture(_payload()))
    with pytest.raises(DataProviderError, match="positive"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=0)


def test_satisfies_protocol() -> None:
    from xau_ai.data.base import DataProvider

    assert isinstance(OandaDataProvider("TOKEN"), DataProvider)
