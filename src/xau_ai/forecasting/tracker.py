"""Forecast tracker.

Every forecast is appended to a JSONL journal. On later cycles, forecasts whose
evaluation horizon has passed are graded against the actual price then:

* LONG is CORRECT if price rose above the forecast price, else WRONG;
* SHORT mirrors that;
* FLAT forecasts are SKIPPED (they make no directional claim).

This produces the honest accuracy statistics everything else builds on.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from xau_ai.core.exceptions import XauAiError
from xau_ai.core.models import Candle


class ForecastRecord(BaseModel):
    """One recorded forecast (mutable: it gets graded later)."""

    model_config = ConfigDict(extra="forbid")

    as_of: datetime
    direction: str  # LONG | SHORT | FLAT
    confidence: float = Field(ge=0.0, le=1.0)
    price: float
    horizon_min: int = Field(gt=0)
    outcome: str | None = None  # CORRECT | WRONG | SKIPPED | None=pending
    price_after: float | None = None


class ForecastStats(BaseModel):
    """Aggregate accuracy over a time window."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int
    evaluated: int
    correct: int
    wrong: int
    skipped: int
    pending: int
    accuracy: float  # correct / (correct + wrong), 0 when nothing graded
    long_total: int
    long_correct: int
    short_total: int
    short_correct: int
    avg_confidence: float
    strong_count: int  # forecasts at/above the strong threshold


class ForecastTracker:
    """Append-only JSONL journal of forecasts with delayed grading."""

    def __init__(self, path: str | Path, horizon_min: int = 30, keep_days: int = 35) -> None:
        self._path = Path(path)
        self._horizon = horizon_min
        self._keep = timedelta(days=keep_days)

    # -- persistence ---------------------------------------------------------

    def _load(self) -> list[ForecastRecord]:
        if not self._path.is_file():
            return []
        records: list[ForecastRecord] = []
        with self._path.open(encoding="utf-8") as handle:
            for line_no, raw in enumerate(handle, start=1):
                text = raw.strip()
                if not text:
                    continue
                try:
                    records.append(ForecastRecord.model_validate_json(text))
                except ValueError as exc:
                    raise XauAiError(f"{self._path} line {line_no}: bad record ({exc})") from exc
        return records

    def _save(self, records: Sequence[ForecastRecord]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False))
                handle.write("\n")
        tmp.replace(self._path)

    # -- API -------------------------------------------------------------------

    def record(self, as_of: datetime, direction: str, confidence: float, price: float) -> None:
        """Append a new pending forecast."""
        record = ForecastRecord(
            as_of=as_of,
            direction=direction,
            confidence=confidence,
            price=price,
            horizon_min=self._horizon,
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False))
            handle.write("\n")

    def evaluate_pending(self, candles: Sequence[Candle]) -> int:
        """Grade pending forecasts whose horizon lies inside ``candles``.

        Returns the number of newly graded records. Also prunes records older
        than ``keep_days``.
        """
        records = self._load()
        if not records:
            return 0
        if not candles:
            return 0

        newest = candles[-1].timestamp
        graded = 0
        for record in records:
            if record.outcome is not None:
                continue
            due = record.as_of + timedelta(minutes=record.horizon_min)
            if due > newest:
                continue  # not yet due
            price_after = self._price_at(candles, due)
            if price_after is None:
                continue  # horizon fell in a data gap; try next cycle
            record.price_after = price_after
            record.outcome = self._grade(record.direction, record.price, price_after)
            graded += 1

        cutoff = newest - self._keep
        kept = [r for r in records if r.as_of >= cutoff]
        if graded or len(kept) != len(records):
            self._save(kept)
        return graded

    @staticmethod
    def _price_at(candles: Sequence[Candle], due: datetime) -> float | None:
        for candle in candles:
            if candle.timestamp >= due:
                return candle.close
        return None

    @staticmethod
    def _grade(direction: str, price: float, price_after: float) -> str:
        if direction == "LONG":
            return "CORRECT" if price_after > price else "WRONG"
        if direction == "SHORT":
            return "CORRECT" if price_after < price else "WRONG"
        return "SKIPPED"

    def stats(self, now: datetime, window_hours: int = 24, strong: float = 0.85) -> ForecastStats:
        """Accuracy stats over the last ``window_hours``."""
        since = now - timedelta(hours=window_hours)
        window = [r for r in self._load() if r.as_of >= since]

        correct = [r for r in window if r.outcome == "CORRECT"]
        wrong = [r for r in window if r.outcome == "WRONG"]
        skipped = [r for r in window if r.outcome == "SKIPPED"]
        pending = [r for r in window if r.outcome is None]
        graded = len(correct) + len(wrong)

        def _dir(records: list[ForecastRecord], direction: str) -> int:
            return sum(1 for r in records if r.direction == direction)

        return ForecastStats(
            total=len(window),
            evaluated=graded + len(skipped),
            correct=len(correct),
            wrong=len(wrong),
            skipped=len(skipped),
            pending=len(pending),
            accuracy=len(correct) / graded if graded else 0.0,
            long_total=_dir(correct, "LONG") + _dir(wrong, "LONG"),
            long_correct=_dir(correct, "LONG"),
            short_total=_dir(correct, "SHORT") + _dir(wrong, "SHORT"),
            short_correct=_dir(correct, "SHORT"),
            avg_confidence=(sum(r.confidence for r in window) / len(window) if window else 0.0),
            strong_count=sum(1 for r in window if r.confidence >= strong),
        )
