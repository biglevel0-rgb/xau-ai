"""Tests for the CSV data provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from xau_ai.core.exceptions import DataProviderError
from xau_ai.core.models import Timeframe
from xau_ai.data.csv_provider import CsvDataProvider

_CSV = """timestamp,open,high,low,close,volume
2026-07-02T15:00:00,3350,3352,3349,3351,100
2026-07-02T15:05:00,3351,3353,3350,3352,120
2026-07-02T15:10:00,3352,3354,3351,3353,90
"""


def _make_file(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_candles_oldest_to_newest(tmp_path: Path) -> None:
    _make_file(tmp_path, "XAUUSD_M5.csv", _CSV)
    provider = CsvDataProvider(tmp_path)
    candles = provider.get_candles("XAUUSD", Timeframe.M5, count=10)
    assert len(candles) == 3
    assert candles[0].close == 3351
    assert candles[-1].close == 3353


def test_count_limits_to_most_recent(tmp_path: Path) -> None:
    _make_file(tmp_path, "XAUUSD_M5.csv", _CSV)
    provider = CsvDataProvider(tmp_path)
    candles = provider.get_candles("XAUUSD", Timeframe.M5, count=2)
    assert len(candles) == 2
    assert candles[0].close == 3352
    assert candles[1].close == 3353


def test_unsorted_input_is_sorted(tmp_path: Path) -> None:
    rows = _CSV.strip().splitlines()
    shuffled = "\n".join([rows[0], rows[3], rows[1], rows[2]]) + "\n"
    _make_file(tmp_path, "XAUUSD_M5.csv", shuffled)
    provider = CsvDataProvider(tmp_path)
    candles = provider.get_candles("XAUUSD", Timeframe.M5, count=10)
    assert [c.close for c in candles] == [3351, 3352, 3353]


def test_missing_file_raises(tmp_path: Path) -> None:
    provider = CsvDataProvider(tmp_path)
    with pytest.raises(DataProviderError, match="no data file"):
        provider.get_candles("XAUUSD", Timeframe.M1, count=5)


def test_missing_column_raises(tmp_path: Path) -> None:
    no_volume = "timestamp,open,high,low,close\n2026-07-02T15:00:00,1,2,0,1\n"
    _make_file(tmp_path, "XAUUSD_M5.csv", no_volume)
    provider = CsvDataProvider(tmp_path)
    with pytest.raises(DataProviderError, match="missing columns"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=5)


def test_bad_row_raises(tmp_path: Path) -> None:
    bad = "timestamp,open,high,low,close,volume\n2026-07-02T15:00:00,x,2,0,1,10\n"
    _make_file(tmp_path, "XAUUSD_M5.csv", bad)
    provider = CsvDataProvider(tmp_path)
    with pytest.raises(DataProviderError, match="bad row"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=5)


def test_utf8_bom_is_tolerated(tmp_path: Path) -> None:
    path = tmp_path / "XAUUSD_M5.csv"
    path.write_text(_CSV, encoding="utf-8-sig")  # write with BOM
    provider = CsvDataProvider(tmp_path)
    candles = provider.get_candles("XAUUSD", Timeframe.M5, count=10)
    assert len(candles) == 3


def test_non_positive_count_raises(tmp_path: Path) -> None:
    _make_file(tmp_path, "XAUUSD_M5.csv", _CSV)
    provider = CsvDataProvider(tmp_path)
    with pytest.raises(DataProviderError, match="positive"):
        provider.get_candles("XAUUSD", Timeframe.M5, count=0)
