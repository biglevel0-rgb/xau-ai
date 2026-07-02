"""Tests for performance metrics."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from xau_ai.core.models import Direction
from xau_ai.performance.metrics import TradeOutcome, TradeResult, compute_performance


def _trade(pnl_r: float, hour: int = 13) -> TradeResult:
    ts = datetime(2026, 7, 2, hour, 0, 0)
    outcome = TradeOutcome.WIN if pnl_r > 0 else TradeOutcome.LOSS
    return TradeResult(
        direction=Direction.LONG,
        entry=3300.0,
        exit_price=3300.0 + pnl_r,
        pnl_r=pnl_r,
        outcome=outcome,
        entry_time=ts,
        exit_time=ts + timedelta(minutes=30),
    )


def test_empty_report() -> None:
    report = compute_performance([])
    assert report.trades == 0
    assert report.win_rate == 0.0
    assert report.profit_factor == 0.0


def test_basic_metrics() -> None:
    # Three wins of +2R, two losses of -1R.
    trades = [_trade(2.0), _trade(2.0), _trade(2.0), _trade(-1.0), _trade(-1.0)]
    report = compute_performance(trades)
    assert report.trades == 5
    assert report.wins == 3
    assert report.losses == 2
    assert report.win_rate == 0.6
    assert report.total_r == 4.0
    assert report.expectancy_r == 0.8
    assert report.profit_factor == 3.0  # 6 / 2


def test_no_losses_profit_factor_is_gross_win() -> None:
    report = compute_performance([_trade(2.0), _trade(1.0)])
    assert report.profit_factor == 3.0  # no losses -> gross win


def test_max_drawdown() -> None:
    # Equity path: -1, -1 (dd 2), then +2, +2.
    trades = [_trade(-1.0), _trade(-1.0), _trade(2.0), _trade(2.0)]
    report = compute_performance(trades)
    assert report.max_drawdown_r == 2.0


def test_sharpe_positive_for_positive_expectancy() -> None:
    trades = [_trade(2.0), _trade(2.0), _trade(-1.0)]
    report = compute_performance(trades)
    assert report.sharpe > 0.0
    assert report.sortino > 0.0


def test_all_equal_wins_zero_std_sharpe_zero() -> None:
    report = compute_performance([_trade(1.0), _trade(1.0), _trade(1.0)])
    assert report.sharpe == 0.0  # zero variance
    assert report.sortino == 0.0  # no downside


def test_by_hour_win_rate() -> None:
    trades = [_trade(2.0, hour=13), _trade(-1.0, hour=13), _trade(2.0, hour=8)]
    report = compute_performance(trades)
    assert report.by_hour_win_rate[13] == 0.5
    assert report.by_hour_win_rate[8] == 1.0


def test_recovery_factor() -> None:
    trades = [_trade(-1.0), _trade(2.0), _trade(2.0)]  # total 3 R, max dd 1 R
    report = compute_performance(trades)
    assert math.isclose(report.recovery_factor, 3.0)


def test_recovery_factor_negative_for_net_loss() -> None:
    # Regression: caught on real market data. A losing strategy must produce a
    # negative recovery factor, not a validation error.
    trades = [_trade(-1.0), _trade(-1.0), _trade(0.5)]  # total -1.5 R, dd 2 R
    report = compute_performance(trades)
    assert report.recovery_factor == pytest.approx(-0.75)
    assert report.total_r == pytest.approx(-1.5)
