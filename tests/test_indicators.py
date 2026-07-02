"""Tests for numeric indicators."""

from __future__ import annotations

from datetime import datetime

import pytest

from xau_ai.analysis.indicators import atr, clamp01, correlation, ema, vwap
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


class TestVwap:
    def test_equals_typical_when_volume_uniform(self) -> None:
        ts = datetime(2026, 7, 2, 8, 0, 0)
        candles = [
            Candle(timestamp=ts, open=10, high=12, low=6, close=9, volume=100),  # typical 9
            Candle(timestamp=ts, open=10, high=15, low=9, close=9, volume=100),  # typical 11
        ]
        assert vwap(candles) == pytest.approx(10.0)  # (9+11)/2

    def test_weights_by_volume(self) -> None:
        ts = datetime(2026, 7, 2, 8, 0, 0)
        candles = [
            Candle(timestamp=ts, open=9, high=9, low=9, close=9, volume=1),
            Candle(timestamp=ts, open=99, high=99, low=99, close=99, volume=99),
        ]
        assert vwap(candles) == pytest.approx((9 * 1 + 99 * 99) / 100)

    def test_zero_volume_raises(self) -> None:
        ts = datetime(2026, 7, 2, 8, 0, 0)
        candle = Candle(timestamp=ts, open=9, high=9, low=9, close=9, volume=0)
        with pytest.raises(ValueError, match="volume must be positive"):
            vwap([candle])


class TestCorrelation:
    def test_perfect_positive(self) -> None:
        xs = [1.0, 2.0, 3.0, 4.0]
        assert correlation(xs, [2.0, 4.0, 6.0, 8.0]) == pytest.approx(1.0)

    def test_perfect_negative(self) -> None:
        xs = [1.0, 2.0, 3.0, 4.0]
        assert correlation(xs, [8.0, 6.0, 4.0, 2.0]) == pytest.approx(-1.0)

    def test_constant_series_is_zero(self) -> None:
        assert correlation([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]) == 0.0

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            correlation([1.0, 2.0], [1.0])

    def test_too_few_points_raises(self) -> None:
        with pytest.raises(ValueError, match="at least two"):
            correlation([1.0], [1.0])


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
