"""News providers.

All providers implement :class:`NewsProvider`, so calendar sources (CSV export,
ForexFactory, an API) plug in without changing the news skill.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import ValidationError

from xau_ai.core.exceptions import DataProviderError
from xau_ai.data.news.events import NewsEvent, NewsImpact

_REQUIRED_COLUMNS = ("timestamp", "impact", "title")


@runtime_checkable
class NewsProvider(Protocol):
    """Source of scheduled economic events."""

    def events(self) -> list[NewsEvent]:
        """Return all known events."""
        ...


class StaticNewsProvider:
    """In-memory provider (used for tests and as a safe empty default)."""

    def __init__(self, events: list[NewsEvent] | None = None) -> None:
        self._events = list(events) if events else []

    def events(self) -> list[NewsEvent]:
        return list(self._events)


class CsvNewsProvider:
    """Load events from a CSV: ``timestamp,impact,title[,currency]``."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def events(self) -> list[NewsEvent]:
        if not self._path.is_file():
            raise DataProviderError(f"news file not found: {self._path}")
        events: list[NewsEvent] = []
        with self._path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise DataProviderError(f"empty news CSV: {self._path}")
            columns = {name.strip().lower() for name in reader.fieldnames}
            missing = [c for c in _REQUIRED_COLUMNS if c not in columns]
            if missing:
                raise DataProviderError(f"{self._path} missing columns: {', '.join(missing)}")
            for line_no, row in enumerate(reader, start=2):
                events.append(self._parse(row, line_no))
        return events

    def _parse(self, row: dict[str, str], line_no: int) -> NewsEvent:
        normalized = {(k.strip().lower() if k else ""): v for k, v in row.items()}
        try:
            return NewsEvent(
                time=datetime.fromisoformat(normalized["timestamp"].strip()),
                impact=NewsImpact(normalized["impact"].strip().lower()),
                title=normalized["title"].strip(),
                currency=normalized.get("currency", "").strip(),
            )
        except (KeyError, ValueError, ValidationError) as exc:
            raise DataProviderError(f"{self._path} line {line_no}: bad event ({exc})") from exc
