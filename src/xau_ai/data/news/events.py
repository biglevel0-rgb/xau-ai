"""News event model."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class NewsImpact(StrEnum):
    """Event importance (red/orange/yellow folder)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        """Numeric severity for threshold comparisons (HIGH is greatest)."""
        return {NewsImpact.LOW: 1, NewsImpact.MEDIUM: 2, NewsImpact.HIGH: 3}[self]


class NewsEvent(BaseModel):
    """A scheduled economic event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    time: datetime
    title: str
    impact: NewsImpact
    currency: str = ""
