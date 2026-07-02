"""CSV-backed data provider.

Reads OHLCV bars from CSV files, one file per (symbol, timeframe), named
``<SYMBOL>_<TIMEFRAME>.csv`` (e.g. ``XAUUSD_M5.csv``) inside a base directory.

Expected header (case-insensitive): ``timestamp,open,high,low,close,volume``.
``timestamp`` is ISO-8601. This provider needs no external service, so it powers
unit tests and backtesting.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from xau_ai.core.exceptions import DataProviderError
from xau_ai.core.models import Candle, Timeframe

_REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


class CsvDataProvider:
    """Load candles from per-symbol/timeframe CSV files in ``base_dir``."""

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)

    def _file_for(self, symbol: str, timeframe: Timeframe) -> Path:
        return self._base_dir / f"{symbol}_{timeframe.value}.csv"

    def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int,
    ) -> list[Candle]:
        """Return up to ``count`` most recent candles, oldest -> newest."""
        if count <= 0:
            raise DataProviderError(f"count must be positive, got {count}")

        path = self._file_for(symbol, timeframe)
        if not path.is_file():
            raise DataProviderError(f"no data file for {symbol} {timeframe.value}: {path}")

        candles = self._read_all(path)
        candles.sort(key=lambda c: c.timestamp)
        return candles[-count:]

    @staticmethod
    def _read_all(path: Path) -> list[Candle]:
        candles: list[Candle] = []
        # utf-8-sig strips a leading BOM (common in Excel/Windows CSV exports),
        # which would otherwise corrupt the first header name.
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise DataProviderError(f"empty CSV: {path}")
            columns = {name.strip().lower() for name in reader.fieldnames}
            missing = [c for c in _REQUIRED_COLUMNS if c not in columns]
            if missing:
                raise DataProviderError(f"{path} missing columns: {', '.join(missing)}")
            for line_no, row in enumerate(reader, start=2):
                candles.append(CsvDataProvider._parse_row(row, path, line_no))
        if not candles:
            raise DataProviderError(f"no rows in {path}")
        return candles

    @staticmethod
    def _parse_row(row: dict[str, str], path: Path, line_no: int) -> Candle:
        normalized = {(k.strip().lower() if k else ""): v for k, v in row.items()}
        try:
            return Candle(
                timestamp=datetime.fromisoformat(normalized["timestamp"].strip()),
                open=float(normalized["open"]),
                high=float(normalized["high"]),
                low=float(normalized["low"]),
                close=float(normalized["close"]),
                volume=float(normalized["volume"]),
            )
        except (KeyError, ValueError, ValidationError) as exc:
            raise DataProviderError(f"{path} line {line_no}: bad row ({exc})") from exc
