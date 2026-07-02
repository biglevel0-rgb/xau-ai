"""Tests for the backtester."""

from __future__ import annotations

import pytest

from xau_ai.backtesting.backtester import Backtester
from xau_ai.core.models import MarketContext, Signal, SignalType, Timeframe
from xau_ai.performance.metrics import TradeOutcome, TradeResult

from .conftest import ohlc_candles

OHLC = tuple[float, float, float, float]


class FakeSource:
    """Emits one LONG/SHORT signal when the history reaches ``trigger_len`` bars."""

    def __init__(
        self,
        trigger_len: int,
        signal_type: SignalType,
        risk: float = 5.0,
        rr: float = 2.0,
    ) -> None:
        self._trigger_len = trigger_len
        self._signal_type = signal_type
        self._risk = risk
        self._rr = rr

    def analyze(self, ctx: MarketContext) -> Signal:
        bars = ctx.candles(Timeframe.M5)
        last = bars[-1]
        if len(bars) != self._trigger_len:
            return Signal(
                signal_type=SignalType.NO_TRADE,
                symbol=ctx.symbol,
                timeframe=Timeframe.M5,
                as_of=ctx.as_of,
                confidence=0.0,
            )
        entry = last.close
        stop = entry - self._risk if self._signal_type is SignalType.LONG else entry + self._risk
        return Signal(
            signal_type=self._signal_type,
            symbol=ctx.symbol,
            timeframe=Timeframe.M5,
            as_of=ctx.as_of,
            confidence=0.9,
            entry=entry,
            stop_loss=stop,
            risk_reward=self._rr,
        )


def _run(
    rows: list[OHLC], signal_type: SignalType, trigger_len: int = 5
) -> list[TradeResult]:
    candles = ohlc_candles(rows)
    source = FakeSource(trigger_len, signal_type)
    return Backtester(source, warmup=3).run(candles)


def test_long_win() -> None:
    rows: list[OHLC] = [
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3301.0),
        (3301.0, 3302.0, 3300.0, 3302.0),
        (3302.0, 3303.0, 3301.0, 3303.0),
        (3301.0, 3301.0, 3299.0, 3300.0),  # entry bar (close 3300, target 3310)
        (3300.0, 3316.0, 3300.0, 3315.0),  # high 3316 >= target -> WIN
        (3315.0, 3316.0, 3314.0, 3315.0),
        (3315.0, 3316.0, 3314.0, 3315.0),
    ]
    trades = _run(rows, SignalType.LONG)
    assert len(trades) == 1
    assert trades[0].outcome is TradeOutcome.WIN
    assert trades[0].pnl_r == 2.0


def test_long_loss() -> None:
    rows: list[OHLC] = [
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3301.0),
        (3301.0, 3302.0, 3300.0, 3302.0),
        (3302.0, 3303.0, 3301.0, 3303.0),
        (3301.0, 3301.0, 3299.0, 3300.0),  # entry 3300, stop 3295
        (3300.0, 3301.0, 3294.0, 3295.0),  # low 3294 <= stop -> LOSS
        (3295.0, 3296.0, 3294.0, 3295.0),
        (3295.0, 3296.0, 3294.0, 3295.0),
    ]
    trades = _run(rows, SignalType.LONG)
    assert len(trades) == 1
    assert trades[0].outcome is TradeOutcome.LOSS
    assert trades[0].pnl_r == -1.0


def test_timeout_exits_at_last_close() -> None:
    rows: list[OHLC] = [
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3301.0),
        (3301.0, 3302.0, 3300.0, 3302.0),
        (3302.0, 3303.0, 3301.0, 3303.0),
        (3301.0, 3301.0, 3299.0, 3300.0),  # entry 3300 (target 3310, stop 3295)
        (3300.0, 3304.0, 3300.0, 3303.0),  # never reaches target/stop
        (3303.0, 3304.0, 3302.0, 3303.0),
        (3303.0, 3304.0, 3302.0, 3303.0),
    ]
    trades = _run(rows, SignalType.LONG)
    assert len(trades) == 1
    assert trades[0].outcome is TradeOutcome.TIMEOUT
    assert trades[0].pnl_r == pytest.approx((3303.0 - 3300.0) / 5.0)  # 0.6 R


def test_short_win() -> None:
    rows: list[OHLC] = [
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3300.0),
        (3300.0, 3301.0, 3299.0, 3300.0),  # entry 3300, target 3290, stop 3305
        (3300.0, 3301.0, 3289.0, 3290.0),  # low 3289 <= target -> WIN
        (3290.0, 3291.0, 3289.0, 3290.0),
        (3290.0, 3291.0, 3289.0, 3290.0),
    ]
    trades = _run(rows, SignalType.SHORT)
    assert len(trades) == 1
    assert trades[0].outcome is TradeOutcome.WIN
    assert trades[0].direction.value == "SHORT"


def test_no_signals_no_trades() -> None:
    rows: list[OHLC] = [(3300.0, 3301.0, 3299.0, 3300.0)] * 8
    trades = _run(rows, SignalType.LONG, trigger_len=999)  # never triggers
    assert trades == []
