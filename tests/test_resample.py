"""Tests for the M1 resampler."""

from __future__ import annotations

from datetime import datetime, timedelta

from xau_ai.core.models import Candle, Timeframe
from xau_ai.data.resample import resample


def _m1(start: datetime, prices: list[float]) -> list[Candle]:
    return [
        Candle(
            timestamp=start + timedelta(minutes=i),
            open=p,
            high=p + 1.0,
            low=p - 1.0,
            close=p,
            volume=10.0,
        )
        for i, p in enumerate(prices)
    ]


def test_m1_passthrough() -> None:
    candles = _m1(datetime(2026, 7, 2, 15, 0), [1.0, 2.0, 3.0])
    assert resample(candles, Timeframe.M1) == candles


def test_empty_input() -> None:
    assert resample([], Timeframe.M5) == []


def test_m5_aggregation() -> None:
    # 10 aligned M1 bars -> exactly two M5 bars.
    start = datetime(2026, 7, 2, 15, 0)
    candles = _m1(start, [10.0, 12.0, 11.0, 14.0, 13.0, 20.0, 22.0, 21.0, 24.0, 23.0])
    out = resample(candles, Timeframe.M5)
    assert len(out) == 2
    first, second = out
    assert first.timestamp == start
    assert first.open == 10.0
    assert first.close == 13.0
    assert first.high == 15.0  # max(price+1) in bucket
    assert first.low == 9.0
    assert first.volume == 50.0
    assert second.timestamp == start + timedelta(minutes=5)
    assert second.close == 23.0


def test_trailing_partial_bucket_included() -> None:
    start = datetime(2026, 7, 2, 15, 0)
    candles = _m1(start, [10.0] * 7)  # 5 full + 2 into next bucket
    out = resample(candles, Timeframe.M5)
    assert len(out) == 2
    assert out[1].volume == 20.0  # partial bucket of 2 bars


def test_unaligned_start_buckets_correctly() -> None:
    # Starting at :03 -> first bucket is 15:00 (2 bars), then 15:05 (5 bars).
    start = datetime(2026, 7, 2, 15, 3)
    candles = _m1(start, [10.0] * 7)
    out = resample(candles, Timeframe.M5)
    assert out[0].timestamp == datetime(2026, 7, 2, 15, 0)
    assert out[0].volume == 20.0
    assert out[1].timestamp == datetime(2026, 7, 2, 15, 5)
    assert out[1].volume == 50.0


def test_m15_aggregation() -> None:
    start = datetime(2026, 7, 2, 15, 0)
    candles = _m1(start, [float(i) for i in range(30)])
    out = resample(candles, Timeframe.M15)
    assert len(out) == 2
    assert out[0].close == 14.0
    assert out[1].close == 29.0


def test_unsorted_input_is_sorted() -> None:
    start = datetime(2026, 7, 2, 15, 0)
    candles = _m1(start, [1.0, 2.0, 3.0, 4.0, 5.0])
    out = resample(list(reversed(candles)), Timeframe.M5)
    assert len(out) == 1
    assert out[0].open == 1.0
    assert out[0].close == 5.0
