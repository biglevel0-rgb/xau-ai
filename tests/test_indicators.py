"""Tests for numeric indicators."""

from __future__ import annotations

from datetime import datetime

import pytest

from xau_ai.analysis.indicators import atr, clamp01, ema
from xau_ai.core.models import Candle


class TestClamp01:
    def test_within_range(self) -> None:
        assert clamp01(0.5) == 0.5

    def test_below(self) -> None:
        assert clamp01(-3.0) == 0.0

    def test_above(self) -> None:
        assert clamp01(2.0) == 1.0


class TestEma:
    def test_empty(self) -> None:
        assert ema([], 5) == []

    def test_seed_is_first_value(self) -> None:
        assert ema([10.0, 20.0], 1)[0] == 10.0

    def test_constant_series_is_constant(self) -> None:
        result = ema([5.0] * 10, 4)
        assert all(abs(v - 5.0) < 1e-9 for v in result)

    def test_rising_series_lags_below_price(self) -> None:
        prices = [float(i) for i in range(1, 21)]
        result = ema(prices, 5)
        assert result[-1] < prices[-1]  # EMA lags a steady rise

    def test_invalid_period(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            ema([1.0], 0)


def _flat_candles(n: int, price: float = 100.0, rng: float = 2.0) -> list[Candle]:
    ts = datetime(2026, 7, 2, 8, 0, 0)
    return [
        Candle(timestamp=ts, open=price, high=price + rng, low=price - rng, close=price, volume=1)
        for _ in range(n)
    ]


class TestAtr:
    def test_constant_range(self) -> None:
        # Every bar spans 4.0 (high-low), no gaps -> ATR == 4.0.
        assert atr(_flat_candles(30), 14) == pytest.approx(4.0)

    def test_insufficient_candles(self) -> None:
        with pytest.raises(ValueError, match="at least"):
            atr(_flat_candles(5), 14)

    def test_invalid_period(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            atr(_flat_candles(30), 0)
