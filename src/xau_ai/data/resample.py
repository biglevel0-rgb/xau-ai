"""Resample candles to a higher timeframe.

Building M5/M15 locally from fetched M1 bars means one API request serves
several timeframes — essential to stay inside free-tier rate limits.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from xau_ai.core.exceptions import DataProviderError
from xau_ai.core.models import Candle, Timeframe

_MINUTES: dict[Timeframe, int] = {
    Timeframe.M1: 1,
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
}


def _bucket_start(ts: datetime, minutes: int) -> datetime:
    """Floor ``ts`` to the start of its ``minutes``-wide bucket (day-aligned)."""
    minutes_into_day = ts.hour * 60 + ts.minute
    floored = minutes_into_day - (minutes_into_day % minutes)
    midnight = ts.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight + timedelta(minutes=floored)


def resample(candles: Sequence[Candle], target: Timeframe) -> list[Candle]:
    """Aggregate ``candles`` (assumed M1, oldest -> newest) into ``target`` bars.

    Each output bar covers one aligned time bucket: open of the first source
    bar, high/low across the bucket, close of the last, summed volume. The
    (possibly incomplete) trailing bucket is included — it mirrors how a live
    chart shows the forming bar.
    """
    minutes = _MINUTES[target]
    if minutes <= 1:
        return list(candles)
    if not candles:
        return []

    ordered = sorted(candles, key=lambda c: c.timestamp)
    out: list[Candle] = []
    bucket: list[Candle] = []
    bucket_key: datetime | None = None

    for candle in ordered:
        key = _bucket_start(candle.timestamp, minutes)
        if bucket_key is None or key != bucket_key:
            if bucket:
                out.append(_merge(bucket, bucket_key))
            bucket = [candle]
            bucket_key = key
        else:
            bucket.append(candle)
    if bucket:
        out.append(_merge(bucket, bucket_key))
    return out


def _merge(bucket: list[Candle], start: datetime | None) -> Candle:
    if start is None:  # defensive; unreachable with non-empty bucket
        raise DataProviderError("resample bucket without a start time")
    return Candle(
        timestamp=start,
        open=bucket[0].open,
        high=max(c.high for c in bucket),
        low=min(c.low for c in bucket),
        close=bucket[-1].close,
        volume=sum(c.volume for c in bucket),
    )
