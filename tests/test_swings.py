"""Tests for swing-point detection."""

from __future__ import annotations

import pytest

from xau_ai.analysis.swings import find_swings

from .conftest import candles_from_prices


def test_detects_single_peak_and_trough() -> None:
    # Up to a peak at index 2, down to a trough at index 5, up again.
    prices = [10.0, 12.0, 15.0, 12.0, 11.0, 8.0, 10.0, 13.0]
    swings = find_swings(candles_from_prices(prices), left=2, right=2)
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    assert any(s.index == 2 for s in highs)
    assert any(s.index == 5 for s in lows)


def test_edges_are_never_swings() -> None:
    prices = [20.0, 10.0, 11.0, 12.0, 13.0, 25.0]
    swings = find_swings(candles_from_prices(prices), left=2, right=2)
    assert all(2 <= s.index <= len(prices) - 3 for s in swings)


def test_invalid_params() -> None:
    with pytest.raises(ValueError, match=">= 1"):
        find_swings(candles_from_prices([1.0, 2.0, 3.0]), left=0, right=2)


def test_no_swings_in_monotonic_series() -> None:
    prices = [float(i) for i in range(10)]
    swings = find_swings(candles_from_prices(prices), left=2, right=2)
    assert swings == []
