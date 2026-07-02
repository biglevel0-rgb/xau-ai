"""Backtester.

Walks a candle series bar by bar. At each bar it builds a market context from
history up to that bar and asks a :class:`SignalSource` (e.g. the orchestrator)
for a verdict. On a LONG/SHORT signal it opens one simulated trade and walks
forward until the stop or the R-target is hit (stop wins ties, conservatively),
or the data ends (TIMEOUT, closed at the last price).

Only one position is open at a time; scanning resumes after the trade closes.
Results are expressed in R units by :class:`TradeResult`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from xau_ai.core.models import (
    Candle,
    Direction,
    MarketContext,
    Signal,
    SignalType,
    Timeframe,
)
from xau_ai.performance.metrics import TradeOutcome, TradeResult


@runtime_checkable
class SignalSource(Protocol):
    """Anything that turns a market context into a signal."""

    def analyze(self, ctx: MarketContext) -> Signal: ...


class Backtester:
    """Simulate the signal pipeline over historical candles."""

    def __init__(
        self,
        source: SignalSource,
        symbol: str = "XAUUSD",
        timeframe: Timeframe = Timeframe.M5,
        warmup: int = 60,
    ) -> None:
        self._source = source
        self._symbol = symbol
        self._timeframe = timeframe
        self._warmup = warmup

    def run(self, candles: Sequence[Candle]) -> list[TradeResult]:
        """Return the list of simulated trades over ``candles``."""
        trades: list[TradeResult] = []
        n = len(candles)
        i = max(self._warmup, 1)
        while i < n - 1:
            ctx = MarketContext(
                symbol=self._symbol,
                as_of=candles[i].timestamp,
                series={self._timeframe: list(candles[: i + 1])},
            )
            signal = self._source.analyze(ctx)
            if self._is_actionable(signal):
                trade, exit_index = self._simulate(candles, i, signal)
                trades.append(trade)
                i = exit_index + 1
            else:
                i += 1
        return trades

    @staticmethod
    def _is_actionable(signal: Signal) -> bool:
        return (
            signal.signal_type in (SignalType.LONG, SignalType.SHORT)
            and signal.entry is not None
            and signal.stop_loss is not None
            and signal.risk_reward is not None
        )

    def _simulate(
        self, candles: Sequence[Candle], open_index: int, signal: Signal
    ) -> tuple[TradeResult, int]:
        assert signal.entry is not None and signal.stop_loss is not None
        assert signal.risk_reward is not None

        direction = Direction.LONG if signal.signal_type is SignalType.LONG else Direction.SHORT
        entry = signal.entry
        risk = abs(entry - signal.stop_loss)
        stop = signal.stop_loss
        if direction is Direction.LONG:
            target = entry + signal.risk_reward * risk
        else:
            target = entry - signal.risk_reward * risk

        for j in range(open_index + 1, len(candles)):
            bar = candles[j]
            hit_stop, hit_target = self._touches(direction, bar, stop, target)
            if hit_stop:
                return self._closed(
                    direction, entry, stop, -1.0, TradeOutcome.LOSS, candles[open_index], bar
                ), j
            if hit_target:
                return self._closed(
                    direction,
                    entry,
                    target,
                    signal.risk_reward,
                    TradeOutcome.WIN,
                    candles[open_index],
                    bar,
                ), j

        last = candles[-1]
        pnl_r = self._signed(direction, (last.close - entry) / risk)
        return self._closed(
            direction, entry, last.close, pnl_r, TradeOutcome.TIMEOUT, candles[open_index], last
        ), len(candles) - 1

    @staticmethod
    def _touches(
        direction: Direction, bar: Candle, stop: float, target: float
    ) -> tuple[bool, bool]:
        if direction is Direction.LONG:
            return bar.low <= stop, bar.high >= target
        return bar.high >= stop, bar.low <= target

    @staticmethod
    def _signed(direction: Direction, value: float) -> float:
        return value if direction is Direction.LONG else -value

    @staticmethod
    def _closed(
        direction: Direction,
        entry: float,
        exit_price: float,
        pnl_r: float,
        outcome: TradeOutcome,
        open_bar: Candle,
        close_bar: Candle,
    ) -> TradeResult:
        return TradeResult(
            direction=direction,
            entry=entry,
            exit_price=exit_price,
            pnl_r=pnl_r,
            outcome=outcome,
            entry_time=open_bar.timestamp,
            exit_time=close_bar.timestamp,
        )
