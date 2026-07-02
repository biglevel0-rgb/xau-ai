"""Tests for the forecast tracker (self-verification)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from xau_ai.core.models import Candle
from xau_ai.forecasting.tracker import ForecastTracker

from .conftest import candles_from_prices

T0 = datetime(2026, 7, 2, 12, 0, 0)


def _tracker(tmp_path: Path, horizon: int = 30) -> ForecastTracker:
    return ForecastTracker(tmp_path / "forecasts.jsonl", horizon_min=horizon)


def _candles_after(minutes: int, start_price: float, end_price: float) -> list[Candle]:
    n = minutes + 1
    step = (end_price - start_price) / max(n - 1, 1)
    prices = [start_price + step * i for i in range(n)]
    return candles_from_prices(prices, start=T0, step_min=1)


class TestRecordAndEvaluate:
    def test_long_correct_when_price_rises(self, tmp_path: Path) -> None:
        tracker = _tracker(tmp_path)
        tracker.record(T0, "LONG", 0.6, 3300.0)
        graded = tracker.evaluate_pending(_candles_after(40, 3300.0, 3310.0))
        assert graded == 1
        stats = tracker.stats(T0 + timedelta(hours=1))
        assert stats.correct == 1
        assert stats.long_correct == 1

    def test_long_wrong_when_price_falls(self, tmp_path: Path) -> None:
        tracker = _tracker(tmp_path)
        tracker.record(T0, "LONG", 0.6, 3300.0)
        tracker.evaluate_pending(_candles_after(40, 3300.0, 3290.0))
        stats = tracker.stats(T0 + timedelta(hours=1))
        assert stats.wrong == 1
        assert stats.accuracy == 0.0

    def test_short_correct_when_price_falls(self, tmp_path: Path) -> None:
        tracker = _tracker(tmp_path)
        tracker.record(T0, "SHORT", 0.7, 3300.0)
        tracker.evaluate_pending(_candles_after(40, 3300.0, 3290.0))
        stats = tracker.stats(T0 + timedelta(hours=1))
        assert stats.short_correct == 1
        assert stats.accuracy == 1.0

    def test_flat_is_skipped(self, tmp_path: Path) -> None:
        tracker = _tracker(tmp_path)
        tracker.record(T0, "FLAT", 0.0, 3300.0)
        tracker.evaluate_pending(_candles_after(40, 3300.0, 3310.0))
        stats = tracker.stats(T0 + timedelta(hours=1))
        assert stats.skipped == 1
        assert stats.correct == 0

    def test_not_due_stays_pending(self, tmp_path: Path) -> None:
        tracker = _tracker(tmp_path, horizon=30)
        tracker.record(T0, "LONG", 0.6, 3300.0)
        graded = tracker.evaluate_pending(_candles_after(10, 3300.0, 3305.0))  # only 10 min
        assert graded == 0
        stats = tracker.stats(T0 + timedelta(hours=1))
        assert stats.pending == 1

    def test_already_graded_not_regraded(self, tmp_path: Path) -> None:
        tracker = _tracker(tmp_path)
        tracker.record(T0, "LONG", 0.6, 3300.0)
        candles = _candles_after(40, 3300.0, 3310.0)
        assert tracker.evaluate_pending(candles) == 1
        assert tracker.evaluate_pending(candles) == 0


class TestStats:
    def test_empty_journal(self, tmp_path: Path) -> None:
        stats = _tracker(tmp_path).stats(T0)
        assert stats.total == 0
        assert stats.accuracy == 0.0

    def test_window_excludes_old(self, tmp_path: Path) -> None:
        tracker = _tracker(tmp_path)
        tracker.record(T0 - timedelta(hours=48), "LONG", 0.5, 3300.0)
        tracker.record(T0, "LONG", 0.5, 3300.0)
        stats = tracker.stats(T0 + timedelta(minutes=5), window_hours=24)
        assert stats.total == 1

    def test_strong_count(self, tmp_path: Path) -> None:
        tracker = _tracker(tmp_path)
        tracker.record(T0, "LONG", 0.9, 3300.0)
        tracker.record(T0, "LONG", 0.5, 3300.0)
        stats = tracker.stats(T0 + timedelta(minutes=5))
        assert stats.strong_count == 1

    def test_prune_old_records(self, tmp_path: Path) -> None:
        tracker = ForecastTracker(tmp_path / "f.jsonl", horizon_min=30, keep_days=14)
        tracker.record(T0 - timedelta(days=30), "LONG", 0.5, 3300.0)
        tracker.record(T0, "LONG", 0.5, 3300.0)
        tracker.evaluate_pending(_candles_after(40, 3300.0, 3310.0))
        stats = tracker.stats(T0 + timedelta(hours=1), window_hours=24 * 60)
        assert stats.total == 1  # 30-day-old record pruned
