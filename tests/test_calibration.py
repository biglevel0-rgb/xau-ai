"""Tests for weight calibration."""

from __future__ import annotations

from datetime import datetime

import pytest

from xau_ai.calibration.calibrator import (
    CalibrationResult,
    Calibrator,
    generate_weight_candidates,
    metric_for,
)
from xau_ai.core.exceptions import ConfigError
from xau_ai.core.models import Candle, MarketContext, Timeframe

from .conftest import candles_from_prices, make_settings

AS_OF = datetime(2026, 7, 2, 13, 0, 0)


def _candles(n: int = 80) -> list[Candle]:
    return candles_from_prices([3300.0 + i * 2 for i in range(n)])


def _calibrator() -> Calibrator:
    settings = make_settings(
        confidence_threshold=0.1,
        required_confirmations=("trend",),
        weights={"trend": 0.5, "market_structure": 0.5},
    )
    return Calibrator(settings, timeframe=Timeframe.M5, warmup=55)


class TestCandidateGeneration:
    def test_count_is_uniform_plus_one_per_skill(self) -> None:
        candidates = generate_weight_candidates(["trend", "market_structure"])
        assert len(candidates) == 3  # uniform + 2 emphasised

    def test_each_candidate_sums_to_one(self) -> None:
        for candidate in generate_weight_candidates(["a", "b", "c"]):
            assert sum(candidate.values()) == pytest.approx(1.0)

    def test_emphasis_raises_target_weight(self) -> None:
        candidates = generate_weight_candidates(["a", "b"], emphasis=3.0)
        emphasised = candidates[1]  # emphasises "a"
        assert emphasised["a"] > emphasised["b"]

    def test_empty_names_rejected(self) -> None:
        with pytest.raises(ConfigError, match="at least one"):
            generate_weight_candidates([])


class TestMetricFor:
    def test_known_metric(self) -> None:
        assert metric_for("expectancy") is not None

    def test_unknown_metric_raises(self) -> None:
        with pytest.raises(ConfigError, match="unknown metric"):
            metric_for("nope")


class TestCalibrate:
    def test_returns_result_over_default_candidates(self) -> None:
        result = _calibrator().calibrate(_candles(), metric="expectancy")
        assert isinstance(result, CalibrationResult)
        assert set(result.best_weights) == {"trend", "market_structure"}
        assert sum(result.best_weights.values()) == pytest.approx(1.0)
        assert len(result.ranked) >= 1

    def test_is_deterministic(self) -> None:
        cal = _calibrator()
        candles = _candles()
        first = cal.calibrate(candles, metric="expectancy")
        second = cal.calibrate(candles, metric="expectancy")
        assert first.best_weights == second.best_weights
        assert first.best_score == second.best_score

    def test_explicit_candidates_are_used(self) -> None:
        candidates = [{"trend": 1.0, "market_structure": 0.0}]
        result = _calibrator().calibrate(_candles(), candidates=candidates)
        assert result.best_weights == {"trend": 1.0, "market_structure": 0.0}

    def test_empty_candidates_rejected(self) -> None:
        with pytest.raises(ConfigError, match="no weight candidates"):
            _calibrator().calibrate(_candles(), candidates=[])

    def test_injected_skills_are_used(self) -> None:
        # Inject a single skill so precompute is cheap and deterministic.
        from xau_ai.skills.trend import TrendSkill

        settings = make_settings(
            confidence_threshold=0.1,
            required_confirmations=("trend",),
            weights={"trend": 1.0},
        )
        cal = Calibrator(settings, warmup=55, skills=[TrendSkill()])
        result = cal.calibrate(_candles(), candidates=[{"trend": 1.0}])
        assert result.best_weights == {"trend": 1.0}


def test_cached_source_missing_index_is_no_trade() -> None:
    from xau_ai.calibration.calibrator import _CachedSource
    from xau_ai.signal.generator import SignalGenerator

    generator = SignalGenerator(make_settings(), Timeframe.M5)
    source = _CachedSource(generator, {}, Timeframe.M5)
    ctx = MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: candles_from_prices([3300.0, 3301.0, 3302.0])},
    )
    signal = source.analyze(ctx)
    assert signal.signal_type.value == "NO_TRADE"
