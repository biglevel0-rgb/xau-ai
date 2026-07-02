"""Human-readable signal formatting for notifications."""

from __future__ import annotations

from xau_ai.core.models import Signal, SignalType

_ICON = {SignalType.LONG: "🟢", SignalType.SHORT: "🔴", SignalType.NO_TRADE: "⛔"}


def format_signal(signal: Signal) -> str:
    """Render ``signal`` as a compact multi-line message."""
    lines = [
        f"{_ICON[signal.signal_type]} {signal.symbol} • "
        f"{signal.signal_type.value} • {signal.timeframe.value}",
        f"Confidence: {signal.confidence:.0%}",
    ]
    if signal.entry is not None:
        lines.append(f"Entry: {signal.entry:.2f}")
    if signal.stop_loss is not None:
        lines.append(f"SL: {signal.stop_loss:.2f}")
    for i, take_profit in enumerate(signal.take_profits, start=1):
        lines.append(f"TP{i}: {take_profit:.2f}")
    if signal.risk_reward is not None:
        lines.append(f"RR: 1:{signal.risk_reward:.1f}")
    for reason in signal.reasons:
        lines.append(f"✔ {reason}")
    if signal.invalidation:
        lines.append(f"Invalidation: {signal.invalidation}")
    if signal.journal_id:
        lines.append(f"ID: {signal.journal_id}")
    return "\n".join(lines)
