"""Tests for FVG detection."""

from __future__ import annotations

from .conftest import ohlc_candles


def _bullish_gap_rows() -> list[tuple[float, float, float, float]]:
    # Candle 0 high = 3302; candle 2 low = 3305 -> bullish gap [3302, 3305].
    return [
        (3300.0, 3302.0, 3299.0, 3301.0),
        (3301.0, 3306.0, 3301.0, 3305.0),
        (3305.0, 3308.0, 3305.0, 3307.0),
    ]


def test_detects_bullish_fvg() -> None:
    from xau_ai.analysis.gaps import find_fvgs

    gaps = find_fvgs(ohlc_candles(_bullish_gap_rows()))
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.kind == "bullish"
    assert gap.bottom == 3302.0
    assert gap.top == 3305.0
    assert gap.size == 3.0


def test_detects_bearish_fvg() -> None:
    from xau_ai.analysis.gaps import find_fvgs

    rows = [
        (3310.0, 3311.0, 3305.0, 3306.0),  # low 3305
        (3306.0, 3306.0, 3300.0, 3301.0),
        (3301.0, 3303.0, 3298.0, 3299.0),  # high 3303 < 3305 -> bearish gap
    ]
    gaps = find_fvgs(ohlc_candles(rows))
    assert len(gaps) == 1
    assert gaps[0].kind == "bearish"
    assert gaps[0].bottom == 3303.0
    assert gaps[0].top == 3305.0


def test_no_gap_when_overlapping() -> None:
    from xau_ai.analysis.gaps import find_fvgs

    rows = [
        (3300.0, 3305.0, 3298.0, 3302.0),
        (3302.0, 3306.0, 3300.0, 3304.0),
        (3304.0, 3307.0, 3301.0, 3305.0),  # overlaps candle 0 range
    ]
    assert find_fvgs(ohlc_candles(rows)) == []
