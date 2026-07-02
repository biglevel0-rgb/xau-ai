"""Tests for the risk manager."""

from __future__ import annotations

import pytest

from xau_ai.config.settings import RiskConfig
from xau_ai.core.exceptions import XauAiError
from xau_ai.core.models import Direction
from xau_ai.risk.manager import RiskManager, TradePlan


def _config(**overrides: float) -> RiskConfig:
    base: dict[str, float] = {
        "risk_per_trade_pct": 0.5,
        "min_rr": 2.0,
        "max_daily_loss_pct": 3.0,
        "max_weekly_loss_pct": 6.0,
    }
    base.update(overrides)
    return RiskConfig(**base)  # type: ignore[arg-type]


def test_position_size() -> None:
    # balance 10000 * 0.5% = 50 risk; stop distance 5 * contract 100 = 500/lot -> 0.1 lot.
    manager = RiskManager(_config())
    assert manager.position_size(entry=3350.0, stop_loss=3345.0) == pytest.approx(0.1)


def test_position_size_rounds_down_to_lot_step() -> None:
    manager = RiskManager(_config())
    lots = manager.position_size(entry=3350.0, stop_loss=3343.3)  # non-round result
    assert lots == pytest.approx(round(lots / 0.01) * 0.01, abs=1e-9)
    assert lots <= 50.0 / (abs(3350.0 - 3343.3) * 100.0)  # never rounds risk up


def test_position_size_zero_distance_raises() -> None:
    with pytest.raises(XauAiError, match="stop distance"):
        RiskManager(_config()).position_size(entry=3350.0, stop_loss=3350.0)


def test_build_long_plan() -> None:
    manager = RiskManager(_config())
    plan = manager.build_plan(Direction.LONG, entry=3350.0, atr_value=4.0)
    assert isinstance(plan, TradePlan)
    assert plan.stop_loss == pytest.approx(3350.0 - 1.5 * 4.0)  # 3344
    assert plan.take_profits == pytest.approx((3356.0, 3362.0, 3368.0))
    assert plan.risk_reward == 2.0  # primary_tp_index = 1


def test_build_short_plan() -> None:
    manager = RiskManager(_config())
    plan = manager.build_plan(Direction.SHORT, entry=3350.0, atr_value=4.0)
    assert plan.stop_loss == pytest.approx(3356.0)
    assert plan.take_profits == pytest.approx((3344.0, 3338.0, 3332.0))


def test_build_plan_neutral_raises() -> None:
    with pytest.raises(XauAiError, match="NEUTRAL"):
        RiskManager(_config()).build_plan(Direction.NEUTRAL, entry=3350.0, atr_value=4.0)


def test_build_plan_zero_atr_raises() -> None:
    with pytest.raises(XauAiError, match="ATR"):
        RiskManager(_config()).build_plan(Direction.LONG, entry=3350.0, atr_value=0.0)


def test_trade_plan_rejects_neutral() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TradePlan(
            direction=Direction.NEUTRAL,
            entry=3350.0,
            stop_loss=3344.0,
            take_profits=(3356.0,),
            risk_reward=2.0,
            lots=0.1,
        )
