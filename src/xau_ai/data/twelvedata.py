"""TwelveData cloud data provider.

A REST-based :class:`~xau_ai.data.base.DataProvider` that works on Linux (unlike
MT5), suitable for the production server. The HTTP call is injected as
``transport`` so tests never touch the network.

XAU/USD has no exchange volume on TwelveData, so a missing/blank volume is
treated as 0.0 (skills that need volume simply abstain).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from xau_ai.core.exceptions import DataProviderError
from xau_ai.core.models import Candle, Timeframe
from xau_ai.data.http import get_json

Transport = Callable[[str, dict[str, str]], dict[str, Any]]

_BASE_URL = "https://api.twelvedata.com/time_series"

_INTERVALS: dict[Timeframe, str] = {
    Timeframe.M1: "1min",
    Timeframe.M5: "5min",
    Timeframe.M15: "15min",
    Timeframe.H1: "1h",
    Timeframe.H4: "4h",
}

_DEFAULT_SYMBOL_MAP: dict[str, str] = {
    "XAUUSD": "XAU/USD",
    "XAGUSD": "XAG/USD",
    "EURUSD": "EUR/USD",
    "US10Y": "US10Y",
    "DXY": "DXY",
}


def _http_get_json(url: str, params: dict[str, str]) -> dict[str, Any]:
    """Default transport: GET ``url?params`` and parse JSON."""
    parsed: dict[str, Any] = get_json(url, params)
    return parsed


class TwelveDataProvider:
    """Fetch OHLCV candles from the TwelveData ``time_series`` endpoint."""

    def __init__(
        self,
        api_key: str,
        symbol_map: dict[str, str] | None = None,
        transport: Transport | None = None,
    ) -> None:
        if not api_key:
            raise DataProviderError("TwelveData API key is required")
        self._api_key = api_key
        self._symbol_map = {**_DEFAULT_SYMBOL_MAP, **(symbol_map or {})}
        self._transport = transport or _http_get_json

    def get_candles(self, symbol: str, timeframe: Timeframe, count: int) -> list[Candle]:
        """Return up to ``count`` most recent candles, oldest -> newest."""
        if count <= 0:
            raise DataProviderError(f"count must be positive, got {count}")

        params = {
            "symbol": self._symbol_map.get(symbol, symbol),
            "interval": _INTERVALS[timeframe],
            "outputsize": str(count),
            "apikey": self._api_key,
            "format": "JSON",
            "order": "ASC",
        }
        payload = self._transport(_BASE_URL, params)

        if payload.get("status") == "error":
            raise DataProviderError(f"TwelveData error: {payload.get('message', 'unknown')}")
        values = payload.get("values")
        if not values:
            raise DataProviderError(f"TwelveData returned no values for {symbol} {timeframe.value}")

        candles = [self._row_to_candle(row) for row in values]
        candles.sort(key=lambda c: c.timestamp)
        return candles[-count:]

    @staticmethod
    def _row_to_candle(row: dict[str, Any]) -> Candle:
        try:
            return Candle(
                timestamp=datetime.fromisoformat(str(row["datetime"])),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume") or 0.0),  # XAU often has no volume
            )
        except (KeyError, ValueError, ValidationError) as exc:
            raise DataProviderError(f"TwelveData bad row ({exc}): {row}") from exc
