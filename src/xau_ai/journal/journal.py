"""Append-only trade journal.

Every decision (including NO_TRADE) is written as one JSON object per line so the
file is easy to tail, diff, and stream. Results/PnL are filled in later once a
trade closes, forming the dataset for self-improvement and weight calibration.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from xau_ai.core.exceptions import XauAiError
from xau_ai.core.models import Signal, SignalType


class JournalEntry(BaseModel):
    """One recorded decision."""

    model_config = ConfigDict(extra="forbid")

    journal_id: str
    as_of: datetime
    symbol: str
    signal_type: SignalType
    confidence: float
    entry: float | None = None
    stop_loss: float | None = None
    take_profits: tuple[float, ...] = ()
    risk_reward: float | None = None
    reasons: tuple[str, ...] = ()
    rejections: tuple[str, ...] = ()
    invalidation: str | None = None
    result: str | None = None
    pnl_r: float | None = None

    @classmethod
    def from_signal(cls, signal: Signal, journal_id: str) -> JournalEntry:
        """Build an entry from a signal."""
        return cls(
            journal_id=journal_id,
            as_of=signal.as_of,
            symbol=signal.symbol,
            signal_type=signal.signal_type,
            confidence=signal.confidence,
            entry=signal.entry,
            stop_loss=signal.stop_loss,
            take_profits=signal.take_profits,
            risk_reward=signal.risk_reward,
            reasons=signal.reasons,
            rejections=signal.rejections,
            invalidation=signal.invalidation,
        )


def _make_id(signal: Signal) -> str:
    stamp = signal.as_of.strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{signal.symbol}-{signal.signal_type.value}"


class Journal:
    """Read/append decisions in a JSONL file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def record(self, signal: Signal) -> str:
        """Append ``signal`` as a journal entry and return its id."""
        journal_id = signal.journal_id or _make_id(signal)
        entry = JournalEntry.from_signal(signal, journal_id)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry.model_dump(mode="json"), ensure_ascii=False)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return journal_id

    def entries(self) -> list[JournalEntry]:
        """Read all entries (oldest first). Empty if the file does not exist."""
        if not self._path.is_file():
            return []
        entries: list[JournalEntry] = []
        with self._path.open(encoding="utf-8") as handle:
            for line_no, raw in enumerate(handle, start=1):
                text = raw.strip()
                if not text:
                    continue
                try:
                    entries.append(JournalEntry.model_validate_json(text))
                except ValueError as exc:
                    raise XauAiError(f"{self._path} line {line_no}: bad entry ({exc})") from exc
        return entries
