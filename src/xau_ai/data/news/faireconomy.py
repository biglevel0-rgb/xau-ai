"""Free economic-calendar provider (faireconomy.media weekly JSON feed).

This is the well-known free mirror of the ForexFactory calendar. The feed is a
JSON array of this week's events; we fetch it at most once per ``ttl`` seconds
and cache to disk so the 5-minute analysis loop doesn't hammer the endpoint.
Event times arrive timezone-aware and are normalised to naive UTC to match
candle timestamps.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xau_ai.core.exceptions import DataProviderError
from xau_ai.data.http import get_json
from xau_ai.data.news.events import NewsEvent, NewsImpact

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

Transport = Callable[[str], Any]

_IMPACT_MAP = {
    "high": NewsImpact.HIGH,
    "medium": NewsImpact.MEDIUM,
    "low": NewsImpact.LOW,
    "holiday": NewsImpact.LOW,
}


def _fetch_feed(url: str) -> Any:
    return get_json(url)


class FaireconomyNewsProvider:
    """Weekly ForexFactory-style calendar with a disk cache."""

    def __init__(
        self,
        cache_path: str | Path = "journal/news_cache.json",
        ttl_seconds: int = 3600,
        currencies: tuple[str, ...] = ("USD",),
        transport: Transport | None = None,
        url: str = FEED_URL,
    ) -> None:
        self._cache_path = Path(cache_path)
        self._ttl = ttl_seconds
        self._currencies = currencies
        self._transport = transport or _fetch_feed
        self._url = url

    def events(self) -> list[NewsEvent]:
        """Return this week's events for the configured currencies."""
        raw = self._load_cached()
        if raw is None:
            raw = self._transport(self._url)
            self._store_cache(raw)
        if not isinstance(raw, list):
            raise DataProviderError("calendar feed: expected a JSON array")
        events: list[NewsEvent] = []
        for item in raw:
            event = self._parse(item)
            if event is not None:
                events.append(event)
        return events

    def _parse(self, item: Any) -> NewsEvent | None:
        if not isinstance(item, dict):
            return None
        currency = str(item.get("country", "")).upper()
        if self._currencies and currency not in self._currencies:
            return None
        impact = _IMPACT_MAP.get(str(item.get("impact", "")).lower())
        if impact is None:
            return None
        try:
            moment = datetime.fromisoformat(str(item["date"]))
        except (KeyError, ValueError):
            return None
        if moment.tzinfo is not None:
            moment = moment.astimezone(UTC).replace(tzinfo=None)  # naive UTC
        return NewsEvent(
            time=moment,
            title=str(item.get("title", "")).strip() or "(untitled)",
            impact=impact,
            currency=currency,
        )

    # -- cache -----------------------------------------------------------------

    def _load_cached(self) -> Any | None:
        try:
            if not self._cache_path.is_file():
                return None
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if time.time() - float(payload["fetched_at"]) > self._ttl:
                return None
            return payload["data"]
        except (OSError, ValueError, KeyError):
            return None  # unreadable cache -> refetch

    def _store_cache(self, data: Any) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps({"fetched_at": time.time(), "data": data}), encoding="utf-8"
            )
        except OSError:
            pass  # cache is an optimisation; never fail the cycle over it
