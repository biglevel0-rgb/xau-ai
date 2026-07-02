"""Tests for the signal generator (the core verdict logic)."""

from __future__ import annotations

from datetime import datetime

from xau_ai.core.models import Direction, MarketContext, SignalType, SkillResult, Timeframe
from xau_ai.signal.generator import SignalGenerator

from .conftest import candles_from_prices, make_settings

AS_OF = datetime(2026, 7, 2, 15, 0, 0)


def _ctx(n: int = 60) -> MarketContext:
    return MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: candles_from_prices([3300.0 + i * 2 for i in range(n)])},
    )


def _res(
    name: str,
    direction: Direction,
    score: float,
    evidence: tuple[str, ...] = (),
    invalidation: str | None = None,
) -> SkillResult:
    return SkillResult(
        skill_name=name,
        direction=direction,
        score=score,
        evidence=evidence,
        invalidation=invalidation,
    )


def _long_results() -> list[SkillResult]:
    return [
        _res("trend", Direction.LONG, 0.9, evidence=("EMA20 above EMA50",)),
        _res("market_structure", Direction.LONG, 0.9, evidence=("Bullish BOS",)),
    ]


def test_valid_long_signal() -> None:
    gen = SignalGenerator(make_settings(confidence_threshold=0.6))
    signal = gen.generate(_ctx(), _long_results())
    assert signal.signal_type is SignalType.LONG
    assert signal.entry is not None
    assert signal.stop_loss is not None
    assert signal.risk_reward == 2.0
    assert any("trend" in r for r in signal.reasons)
    assert signal.invalidation is not None


def test_no_trade_on_low_confidence() -> None:
    gen = SignalGenerator(make_settings(confidence_threshold=0.9))
    signal = gen.generate(
        _ctx(),
        [_res("trend", Direction.LONG, 0.3), _res("market_structure", Direction.NEUTRAL, 0.0)],
    )
    assert signal.signal_type is SignalType.NO_TRADE
    assert any("confidence" in r for r in signal.rejections)


def test_no_trade_on_missing_confirmation() -> None:
    gen = SignalGenerator(
        make_settings(
            confidence_threshold=0.3, required_confirmations=("trend", "market_structure")
        )
    )
    signal = gen.generate(
        _ctx(),
        [_res("trend", Direction.LONG, 0.9), _res("market_structure", Direction.NEUTRAL, 0.0)],
    )
    assert signal.signal_type is SignalType.NO_TRADE
    assert any("missing confirmations" in r for r in signal.rejections)


def test_no_trade_on_no_consensus() -> None:
    gen = SignalGenerator(make_settings())
    signal = gen.generate(
        _ctx(),
        [_res("trend", Direction.LONG, 0.8), _res("market_structure", Direction.SHORT, 0.8)],
    )
    assert signal.signal_type is SignalType.NO_TRADE
    assert any("consensus" in r for r in signal.rejections)


def test_no_trade_on_insufficient_rr() -> None:
    gen = SignalGenerator(make_settings(confidence_threshold=0.6, min_rr=5.0))
    signal = gen.generate(_ctx(), _long_results())
    assert signal.signal_type is SignalType.NO_TRADE
    assert any("RR" in r for r in signal.rejections)


def test_no_trade_on_insufficient_data() -> None:
    gen = SignalGenerator(make_settings(confidence_threshold=0.6))
    signal = gen.generate(_ctx(n=5), _long_results())
    assert signal.signal_type is SignalType.NO_TRADE
    assert any("insufficient" in r for r in signal.rejections)


def test_invalidation_from_skill_is_used() -> None:
    gen = SignalGenerator(make_settings(confidence_threshold=0.6))
    results = [
        _res("trend", Direction.LONG, 0.9, evidence=("uptrend",)),
        _res(
            "market_structure",
            Direction.LONG,
            0.9,
            evidence=("Bullish BOS",),
            invalidation="close below 3344.00",
        ),
    ]
    signal = gen.generate(_ctx(), results)
    assert signal.invalidation == "close below 3344.00"


def test_no_trade_on_degenerate_atr() -> None:
    gen = SignalGenerator(make_settings(confidence_threshold=0.6))
    ctx = MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: candles_from_prices([3300.0] * 60, wick=0.0)},
    )
    signal = gen.generate(ctx, _long_results())
    assert signal.signal_type is SignalType.NO_TRADE
    assert any("degenerate" in r for r in signal.rejections)


def test_short_signal() -> None:
    gen = SignalGenerator(make_settings(confidence_threshold=0.6))
    ctx = MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: candles_from_prices([3400.0 - i * 2 for i in range(60)])},
    )
    signal = gen.generate(
        ctx,
        [_res("trend", Direction.SHORT, 0.9), _res("market_structure", Direction.SHORT, 0.9)],
    )
    assert signal.signal_type is SignalType.SHORT
    assert signal.stop_loss is not None and signal.entry is not None
    assert signal.stop_loss > signal.entry
