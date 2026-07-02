"""Tests for the trade journal."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from xau_ai.core.exceptions import XauAiError
from xau_ai.core.models import Signal, SignalType, Timeframe
from xau_ai.journal.journal import Journal

AS_OF = datetime(2026, 7, 2, 15, 10, 0)


def _long_signal() -> Signal:
    return Signal(
        signal_type=SignalType.LONG,
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        as_of=AS_OF,
        confidence=0.91,
        entry=3352.6,
        stop_loss=3348.9,
        take_profits=(3357.0, 3363.2),
        risk_reward=2.8,
        reasons=("trend: up",),
    )


def _no_trade_signal() -> Signal:
    return Signal(
        signal_type=SignalType.NO_TRADE,
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        as_of=AS_OF,
        confidence=0.4,
        rejections=("confidence low",),
    )


def test_record_returns_id_and_creates_file(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "sub" / "trades.jsonl")
    journal_id = journal.record(_long_signal())
    assert journal_id == "20260702T151000-XAUUSD-LONG"
    assert journal.path.is_file()


def test_entries_roundtrip(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "trades.jsonl")
    journal.record(_long_signal())
    journal.record(_no_trade_signal())
    entries = journal.entries()
    assert len(entries) == 2
    assert entries[0].signal_type is SignalType.LONG
    assert entries[0].entry == 3352.6
    assert entries[1].signal_type is SignalType.NO_TRADE
    assert entries[1].entry is None


def test_entries_missing_file_is_empty(tmp_path: Path) -> None:
    assert Journal(tmp_path / "none.jsonl").entries() == []


def test_append_is_additive(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "trades.jsonl")
    journal.record(_long_signal())
    journal.record(_long_signal())
    assert len(journal.entries()) == 2


def test_blank_lines_ignored(tmp_path: Path) -> None:
    path = tmp_path / "trades.jsonl"
    journal = Journal(path)
    journal.record(_long_signal())
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
    assert len(journal.entries()) == 1


def test_corrupt_line_raises(tmp_path: Path) -> None:
    path = tmp_path / "trades.jsonl"
    path.write_text("{not valid json}\n", encoding="utf-8")
    with pytest.raises(XauAiError, match="bad entry"):
        Journal(path).entries()
