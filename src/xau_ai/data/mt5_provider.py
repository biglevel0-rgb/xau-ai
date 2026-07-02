"""MetaTrader 5 data provider (local Windows only).

The ``MetaTrader5`` package is Windows-only and requires a running terminal, so
it is an *optional* dependency imported lazily. On the Linux production server
this provider is unavailable by design — use a cloud provider (OANDA / TwelveData)
there. Import failures surface as :class:`DataProviderError`, never at module load.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from xau_ai.core.exceptions import DataProviderError
from xau_ai.core.models import Candle, Timeframe

# Timeframe -> MetaTrader5 constant attribute name (resolved at call time).
_TF_ATTR: dict[Timeframe, str] = {
    Timeframe.M1: "TIMEFRAME_M1",
    Timeframe.M5: "TIMEFRAME_M5",
    Timeframe.M15: "TIMEFRAME_M15",
    Timeframe.H1: "TIMEFRAME_H1",
    Timeframe.H4: "TIMEFRAME_H4",
}


class _Rate(Protocol):
    """Structural view of one MT5 rate row (numpy void or mapping)."""

    def __getitem__(self, field: str) -> Any: ...


def _load_mt5() -> Any:
    """Import the MetaTrader5 module or raise a clear error.

    Returns the untyped third-party module (typed as ``Any``).
    """
    try:
        import MetaTrader5
    except ImportError as exc:
        raise DataProviderError(
            "MetaTrader5 is not installed. Install with `pip install .[mt5]` "
            "on a Windows machine with a running terminal."
        ) from exc
    return MetaTrader5


def _rows_to_candles(rows: Any) -> list[Candle]:
    """Convert MT5 rate rows to candles (pure; testable without MT5)."""
    candles: list[Candle] = []
    for row in rows:
        rate: _Rate = row
        candles.append(
            Candle(
                timestamp=datetime.fromtimestamp(int(rate["time"]), tz=UTC),
                open=float(rate["open"]),
                high=float(rate["high"]),
                low=float(rate["low"]),
                close=float(rate["close"]),
                volume=float(rate["tick_volume"]),
            )
        )
    return candles


class Mt5DataProvider:
    """Fetch OHLCV candles from a MetaTrader 5 terminal.

    Credentials are optional: if omitted, the provider attaches to whichever
    terminal is already running and logged in.
    """

    def __init__(
        self,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
    ) -> None:
        self._login = login
        self._password = password
        self._server = server
        self._mt5: Any = None

    def _ensure_connected(self) -> Any:
        if self._mt5 is not None:
            return self._mt5
        mt5 = _load_mt5()
        if self._login is not None:
            ok = mt5.initialize(login=self._login, password=self._password, server=self._server)
        else:
            ok = mt5.initialize()
        if not ok:
            raise DataProviderError(f"MT5 initialize failed: {mt5.last_error()}")
        self._mt5 = mt5
        return mt5

    def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int,
    ) -> list[Candle]:
        """Return up to ``count`` most recent candles, oldest -> newest."""
        if count <= 0:
            raise DataProviderError(f"count must be positive, got {count}")
        mt5 = self._ensure_connected()
        tf_const = getattr(mt5, _TF_ATTR[timeframe])
        rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, count)
        if rates is None or len(rates) == 0:
            raise DataProviderError(
                f"no MT5 data for {symbol} {timeframe.value}: {mt5.last_error()}"
            )
        return _rows_to_candles(rates)

    def close(self) -> None:
        """Shut down the MT5 connection if it was opened."""
        if self._mt5 is not None:
            self._mt5.shutdown()
            self._mt5 = None
