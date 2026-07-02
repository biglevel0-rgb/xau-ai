"""OANDA v20 data provider (reserve/second source; has real DXY-adjacent FX).

Uses the REST candles endpoint with mid prices. Works on the practice or live
host depending on ``environment``. The HTTP call is injectable for tests.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from xau_ai.core.exceptions import DataProviderError
from xau_ai.core.models import Candle, Timeframe
from xau_ai.data.http import get_json

Transport = Callable[[str, dict[str, str], dict[str, str]], Any]

_HOSTS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}

_GRANULARITY: dict[Timeframe, str] = {
    Timeframe.M1: "M1",
    Timeframe.M5: "M5",
    Timeframe.M15: "M15",
    Timeframe.H1: "H1",
    Timeframe.H4: "H4",
}

_SYMBOL_MAP = {
    "XAUUSD": "XAU_USD",
    "XAGUSD": "XAG_USD",
    "EURUSD": "EUR_USD",
}


def _http_get(url: str, params: dict[str, str], headers: dict[str, str]) -> Any:
    return get_json(url, params, headers)


class OandaDataProvider:
    """Fetch OHLCV candles from OANDA's v20 REST API."""

    def __init__(
        self,
        api_token: str,
        environment: str = "practice",
        transport: Transport | None = None,
    ) -> None:
        if not api_token:
            raise DataProviderError("OANDA API token is required")
        if environment not in _HOSTS:
            raise DataProviderError(f"unknown OANDA environment: {environment!r}")
        self._token = api_token
        self._host = _HOSTS[environment]
        self._transport = transport or _http_get

    def get_candles(self, symbol: str, timeframe: Timeframe, count: int) -> list[Candle]:
        """Return up to ``count`` most recent candles, oldest -> newest."""
        if count <= 0:
            raise DataProviderError(f"count must be positive, got {count}")
        instrument = _SYMBOL_MAP.get(symbol, symbol)
        url = f"{self._host}/v3/instruments/{instrument}/candles"
        params = {
            "granularity": _GRANULARITY[timeframe],
            "count": str(min(count, 5000)),
            "price": "M",
        }
        headers = {"Authorization": f"Bearer {self._token}"}
        payload = self._transport(url, params, headers)

        if not isinstance(payload, dict):
            raise DataProviderError("OANDA: unexpected response shape")
        if "errorMessage" in payload:
            raise DataProviderError(f"OANDA error: {payload['errorMessage']}")
        rows = payload.get("candles")
        if not rows:
            raise DataProviderError(f"OANDA returned no candles for {symbol} {timeframe.value}")

        candles = [self._row_to_candle(row) for row in rows]
        candles.sort(key=lambda c: c.timestamp)
        return candles[-count:]

    @staticmethod
    def _row_to_candle(row: dict[str, Any]) -> Candle:
        try:
            mid = row["mid"]
            stamp = str(row["time"])
            # OANDA: RFC3339 with nanoseconds, e.g. 2026-07-03T01:00:00.000000000Z
            trimmed = stamp.split(".")[0].replace("Z", "")
            moment = datetime.fromisoformat(trimmed)
            if moment.tzinfo is not None:  # defensive; trimmed form is naive
                moment = moment.astimezone(UTC).replace(tzinfo=None)
            return Candle(
                timestamp=moment,
                open=float(mid["o"]),
                high=float(mid["h"]),
                low=float(mid["l"]),
                close=float(mid["c"]),
                volume=float(row.get("volume", 0.0)),
            )
        except (KeyError, ValueError, ValidationError) as exc:
            raise DataProviderError(f"OANDA bad candle ({exc}): {row}") from exc
