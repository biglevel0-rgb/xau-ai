"""Trade results and performance metrics.

All profit/loss is expressed in **R units** (multiples of the risk taken), so the
metrics are independent of account size and position sizing.
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from xau_ai.core.models import Direction


class TradeOutcome(StrEnum):
    """How a simulated trade closed."""

    WIN = "WIN"
    LOSS = "LOSS"
    TIMEOUT = "TIMEOUT"


class TradeResult(BaseModel):
    """A single closed trade, normalised to R units."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    direction: Direction
    entry: float
    exit_price: float
    pnl_r: float
    outcome: TradeOutcome
    entry_time: datetime
    exit_time: datetime


class PerformanceReport(BaseModel):
    """Aggregate statistics over a set of trades."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trades: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    win_rate: float = Field(ge=0.0, le=1.0)
    total_r: float
    expectancy_r: float
    profit_factor: float = Field(ge=0.0)
    max_drawdown_r: float = Field(ge=0.0)
    sharpe: float
    sortino: float
    recovery_factor: float = Field(ge=0.0)
    by_hour_win_rate: dict[int, float] = Field(default_factory=dict)


def _drawdown(pnls: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def _by_hour_win_rate(trades: list[TradeResult]) -> dict[int, float]:
    wins: dict[int, int] = {}
    totals: dict[int, int] = {}
    for trade in trades:
        hour = trade.entry_time.hour
        totals[hour] = totals.get(hour, 0) + 1
        if trade.pnl_r > 0:
            wins[hour] = wins.get(hour, 0) + 1
    return {hour: wins.get(hour, 0) / totals[hour] for hour in sorted(totals)}


def compute_performance(trades: list[TradeResult]) -> PerformanceReport:
    """Compute a :class:`PerformanceReport` from ``trades`` (empty-safe)."""
    n = len(trades)
    if n == 0:
        return PerformanceReport(
            trades=0,
            wins=0,
            losses=0,
            win_rate=0.0,
            total_r=0.0,
            expectancy_r=0.0,
            profit_factor=0.0,
            max_drawdown_r=0.0,
            sharpe=0.0,
            sortino=0.0,
            recovery_factor=0.0,
        )

    pnls = [t.pnl_r for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    total_r = math.fsum(pnls)
    mean = total_r / n

    gross_win = math.fsum(wins)
    gross_loss = abs(math.fsum(losses))
    profit_factor = gross_win / gross_loss if gross_loss > 0 else gross_win

    variance = math.fsum((p - mean) ** 2 for p in pnls) / n
    std = math.sqrt(variance)
    sharpe = mean / std if std > 0 else 0.0

    downside = math.sqrt(math.fsum(min(0.0, p) ** 2 for p in pnls) / n)
    sortino = mean / downside if downside > 0 else 0.0

    max_dd = _drawdown(pnls)
    recovery = total_r / max_dd if max_dd > 0 else max(total_r, 0.0)

    return PerformanceReport(
        trades=n,
        wins=len(wins),
        losses=len(losses),
        win_rate=len(wins) / n,
        total_r=total_r,
        expectancy_r=mean,
        profit_factor=profit_factor,
        max_drawdown_r=max_dd,
        sharpe=sharpe,
        sortino=sortino,
        recovery_factor=recovery,
        by_hour_win_rate=_by_hour_win_rate(trades),
    )
