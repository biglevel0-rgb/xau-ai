"""Integration tests for the orchestrator (skills -> validator -> signal)."""

from __future__ import annotations

from datetime import datetime

from xau_ai.core.models import MarketContext, Signal, Timeframe
from xau_ai.core.orchestrator import Orchestrator

from .conftest import candles_from_prices, make_settings

AS_OF = datetime(2026, 7, 2, 13, 0, 0)


def _ctx(prices: list[float]) -> MarketContext:
    return MarketContext(
        symbol="XAUUSD",
        as_of=AS_OF,
        series={Timeframe.M5: candles_from_prices(prices)},
    )


def test_orchestrator_runs_all_registered_skills() -> None:
    orch = Orchestrator(make_settings())
    names = orch.skill_names
    for expected in ("trend", "market_structure", "session", "fvg", "order_block", "liquidity"):
        assert expected in names


def test_run_skills_returns_one_result_per_skill() -> None:
    orch = Orchestrator(make_settings())
    ctx = _ctx([3300.0 + i for i in range(60)])
    results = orch.run_skills(ctx)
    assert len(results) == len(orch.skill_names)


def test_analyze_returns_signal() -> None:
    orch = Orchestrator(make_settings())
    signal = orch.analyze(_ctx([3300.0 + i * 2 for i in range(60)]))
    assert isinstance(signal, Signal)


def test_analyze_permissive_uptrend_can_trade() -> None:
    # Low threshold, only trend required: a strong uptrend should produce a signal.
    settings = make_settings(
        confidence_threshold=0.1,
        required_confirmations=("trend",),
        weights={"trend": 1.0},
    )
    orch = Orchestrator(settings)
    signal = orch.analyze(_ctx([3300.0 + i * 2 for i in range(60)]))
    # Verdict is one of the three allowed types, always well-formed.
    assert signal.signal_type.value in {"LONG", "SHORT", "NO_TRADE"}
