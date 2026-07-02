"""Signal generator.

Combines the validator's aggregate with a risk-managed trade plan and applies
the hard gates. A directional signal is emitted only when *every* gate passes:

1. the validator has a non-NEUTRAL consensus;
2. all ``required_confirmations`` skills vote that direction;
3. enough data exists to compute ATR and a plan;
4. confidence >= ``confidence_threshold``;
5. the plan's reward:risk >= ``min_rr``.

Otherwise the verdict is NO_TRADE, carrying the exact reasons it was rejected.
"""

from __future__ import annotations

from collections.abc import Sequence

from xau_ai.analysis.indicators import atr
from xau_ai.config.settings import Settings
from xau_ai.core.models import (
    Direction,
    MarketContext,
    Signal,
    SignalType,
    SkillResult,
    Timeframe,
)
from xau_ai.risk.manager import RiskManager
from xau_ai.validator.validator import Aggregate, Validator

_DIRECTION_TO_SIGNAL = {
    Direction.LONG: SignalType.LONG,
    Direction.SHORT: SignalType.SHORT,
}


class SignalGenerator:
    """Produce a :class:`Signal` from a context and its skill results."""

    def __init__(self, settings: Settings, timeframe: Timeframe = Timeframe.M5) -> None:
        self._settings = settings
        self._timeframe = timeframe
        self._validator = Validator(settings.validator)
        self._risk = RiskManager(settings.risk)

    def generate(self, ctx: MarketContext, results: Sequence[SkillResult]) -> Signal:
        """Aggregate ``results``, apply the hard gates, and return the verdict."""
        vetoes = [r for r in results if r.veto]
        if vetoes:
            reasons = tuple(
                f"veto by {r.skill_name}: {r.evidence[0]}"
                if r.evidence
                else f"veto by {r.skill_name}"
                for r in vetoes
            )
            return self._no_trade(ctx, 0.0, reasons, ())

        by_name = {r.skill_name: r for r in results}
        agg = self._validator.aggregate(results)
        reasons = self._collect_reasons(agg, by_name)

        if agg.direction is Direction.NEUTRAL:
            return self._no_trade(ctx, agg.confidence, ("no directional consensus",), reasons)

        candles = ctx.candles(self._timeframe)
        if len(candles) < self._settings.risk.atr_period + 1:
            return self._no_trade(ctx, agg.confidence, ("insufficient data for a plan",), reasons)

        entry = candles[-1].close
        atr_value = atr(candles, self._settings.risk.atr_period)
        if atr_value <= 0:
            return self._no_trade(ctx, agg.confidence, ("degenerate ATR (flat market)",), reasons)

        plan = self._risk.build_plan(agg.direction, entry, atr_value)
        rejections = self._gate(agg, plan.risk_reward)
        if rejections:
            return self._no_trade(ctx, agg.confidence, rejections, reasons)

        invalidation = self._invalidation(agg, by_name, plan.stop_loss)
        return Signal(
            signal_type=_DIRECTION_TO_SIGNAL[agg.direction],
            symbol=ctx.symbol,
            timeframe=self._timeframe,
            as_of=ctx.as_of,
            confidence=agg.confidence,
            entry=entry,
            stop_loss=plan.stop_loss,
            take_profits=plan.take_profits,
            risk_reward=plan.risk_reward,
            reasons=reasons,
            invalidation=invalidation,
        )

    def _gate(self, agg: Aggregate, risk_reward: float) -> tuple[str, ...]:
        rejections: list[str] = []
        missing = [
            name
            for name in self._settings.validator.required_confirmations
            if name not in agg.agreeing
        ]
        if missing:
            rejections.append(f"missing confirmations: {', '.join(missing)}")
        if agg.confidence < self._settings.validator.confidence_threshold:
            rejections.append(
                f"confidence {agg.confidence:.0%} below "
                f"{self._settings.validator.confidence_threshold:.0%}"
            )
        if risk_reward < self._settings.risk.min_rr:
            rejections.append(f"RR {risk_reward:.1f} below {self._settings.risk.min_rr:.1f}")
        return tuple(rejections)

    @staticmethod
    def _collect_reasons(agg: Aggregate, by_name: dict[str, SkillResult]) -> tuple[str, ...]:
        reasons: list[str] = []
        for name in agg.agreeing:
            result = by_name.get(name)
            if result and result.evidence:
                reasons.append(f"{name}: {result.evidence[0]}")
        return tuple(reasons)

    @staticmethod
    def _invalidation(agg: Aggregate, by_name: dict[str, SkillResult], stop_loss: float) -> str:
        for name in ("market_structure", "order_block", "liquidity"):
            result = by_name.get(name)
            if result and result.direction is agg.direction and result.invalidation:
                return result.invalidation
        return f"close beyond stop {stop_loss:.2f}"

    def _no_trade(
        self,
        ctx: MarketContext,
        confidence: float,
        rejections: tuple[str, ...],
        reasons: tuple[str, ...],
    ) -> Signal:
        return Signal(
            signal_type=SignalType.NO_TRADE,
            symbol=ctx.symbol,
            timeframe=self._timeframe,
            as_of=ctx.as_of,
            confidence=confidence,
            reasons=reasons,
            rejections=rejections,
        )
