"""Validator-weight calibration.

Skill results do not depend on the validator weights, so they are computed once
per bar and cached. Each weight candidate then only re-runs the (cheap) validator
+ gate + trade simulation. The candidate maximising the chosen metric wins.

This replaces hand-picked weights with weights justified by historical
performance. It is *not* a promise of future profit — it optimises over the
provided history only, so use out-of-sample data and enough trades.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from pydantic import BaseModel, ConfigDict

from xau_ai.backtesting.backtester import Backtester
from xau_ai.config.settings import Settings, ValidatorConfig
from xau_ai.core.exceptions import ConfigError
from xau_ai.core.models import (
    Candle,
    MarketContext,
    Signal,
    SignalType,
    SkillResult,
    Timeframe,
)
from xau_ai.core.registry import registry
from xau_ai.performance.metrics import PerformanceReport, compute_performance
from xau_ai.signal.generator import SignalGenerator
from xau_ai.skills.base import BaseSkill

Metric = Callable[[PerformanceReport], float]

_METRICS: dict[str, Metric] = {
    "expectancy": lambda r: r.expectancy_r,
    "profit_factor": lambda r: r.profit_factor,
    "total_r": lambda r: r.total_r,
}


def metric_for(name: str) -> Metric:
    """Return the metric function for ``name``."""
    try:
        return _METRICS[name]
    except KeyError as exc:
        valid = ", ".join(sorted(_METRICS))
        raise ConfigError(f"unknown metric {name!r}; valid: {valid}") from exc


def generate_weight_candidates(
    skill_names: Sequence[str], emphasis: float = 2.0
) -> list[dict[str, float]]:
    """Deterministic candidate set: uniform, plus one emphasising each skill."""
    names = list(skill_names)
    if not names:
        raise ConfigError("need at least one skill name to generate candidates")
    uniform = {name: 1.0 / len(names) for name in names}
    candidates: list[dict[str, float]] = [uniform]
    for target in names:
        raw = {name: (emphasis if name == target else 1.0) for name in names}
        total = sum(raw.values())
        candidates.append({name: value / total for name, value in raw.items()})
    return candidates


class CalibrationResult(BaseModel):
    """Best weights found and how every candidate ranked."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    best_weights: dict[str, float]
    best_score: float
    best_report: PerformanceReport
    ranked: tuple[dict[str, float], ...] = ()


class _CachedSource:
    """Signal source that reuses precomputed skill results per bar."""

    def __init__(
        self,
        generator: SignalGenerator,
        cache: dict[int, list[SkillResult]],
        timeframe: Timeframe,
    ) -> None:
        self._generator = generator
        self._cache = cache
        self._tf = timeframe

    def analyze(self, ctx: MarketContext) -> Signal:
        index = len(ctx.candles(self._tf)) - 1
        results = self._cache.get(index)
        if results is None:
            return Signal(
                signal_type=SignalType.NO_TRADE,
                symbol=ctx.symbol,
                timeframe=self._tf,
                as_of=ctx.as_of,
                confidence=0.0,
            )
        return self._generator.generate(ctx, results)


class Calibrator:
    """Search validator weights that maximise a backtest metric."""

    def __init__(
        self,
        settings: Settings,
        timeframe: Timeframe = Timeframe.M5,
        warmup: int = 60,
        symbol: str = "XAUUSD",
        skills: Sequence[BaseSkill] | None = None,
    ) -> None:
        self._settings = settings
        self._tf = timeframe
        self._warmup = warmup
        self._symbol = symbol
        self._skills = list(skills) if skills is not None else [c() for c in registry.all()]

    def _precompute(self, candles: Sequence[Candle]) -> dict[int, list[SkillResult]]:
        cache: dict[int, list[SkillResult]] = {}
        for i in range(self._warmup, len(candles) - 1):
            ctx = MarketContext(
                symbol=self._symbol,
                as_of=candles[i].timestamp,
                series={self._tf: list(candles[: i + 1])},
            )
            cache[i] = [skill.analyze(ctx) for skill in self._skills]
        return cache

    def _settings_with_weights(self, weights: dict[str, float]) -> Settings:
        validator = ValidatorConfig(
            confidence_threshold=self._settings.validator.confidence_threshold,
            weights=weights,
            hard_conditions=self._settings.validator.hard_conditions,
            required_confirmations=self._settings.validator.required_confirmations,
        )
        return self._settings.model_copy(update={"validator": validator})

    def _evaluate(
        self,
        candles: Sequence[Candle],
        cache: dict[int, list[SkillResult]],
        weights: dict[str, float],
    ) -> PerformanceReport:
        generator = SignalGenerator(self._settings_with_weights(weights), self._tf)
        source = _CachedSource(generator, cache, self._tf)
        backtester = Backtester(source, self._symbol, self._tf, warmup=self._warmup)
        return compute_performance(backtester.run(candles))

    def calibrate(
        self,
        candles: Sequence[Candle],
        candidates: Sequence[dict[str, float]] | None = None,
        metric: str = "expectancy",
        min_trades: int = 1,
    ) -> CalibrationResult:
        """Return the best-scoring weights over ``candidates`` (or a default set)."""
        if candidates is None:
            candidates = generate_weight_candidates(tuple(self._settings.validator.weights))
        if not candidates:
            raise ConfigError("no weight candidates to evaluate")

        score_of = metric_for(metric)
        cache = self._precompute(candles)

        scored: list[tuple[dict[str, float], float, PerformanceReport]] = []
        for weights in candidates:
            report = self._evaluate(candles, cache, weights)
            scored.append((weights, score_of(report), report))

        # Prefer candidates that actually traded enough; fall back to all.
        eligible = [s for s in scored if s[2].trades >= min_trades] or scored
        eligible.sort(key=lambda s: (s[1], s[2].trades), reverse=True)
        best_weights, best_score, best_report = eligible[0]
        return CalibrationResult(
            best_weights=best_weights,
            best_score=best_score,
            best_report=best_report,
            ranked=tuple(w for w, _, _ in eligible),
        )
