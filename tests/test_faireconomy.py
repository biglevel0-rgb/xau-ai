"""Tests for the free economic-calendar provider."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from xau_ai.core.exceptions import DataProviderError
from xau_ai.data.news.events import NewsImpact
from xau_ai.data.news.faireconomy import FaireconomyNewsProvider


def _feed() -> list[dict[str, Any]]:
    return [
        {
            "title": "Non-Farm Payrolls",
            "country": "USD",
            "impact": "High",
            "date": "2026-07-03T08:30:00-04:00",
        },
        {
            "title": "ECB Rate",
            "country": "EUR",
            "impact": "High",
            "date": "2026-07-03T07:45:00-04:00",
        },
        {
            "title": "Crude Inventories",
            "country": "USD",
            "impact": "Low",
            "date": "2026-07-03T10:30:00-04:00",
        },
        {"title": "Bad row", "country": "USD", "impact": "High", "date": "not-a-date"},
    ]


def _provider(tmp_path: Path, feed: Any = None) -> FaireconomyNewsProvider:
    calls = {"n": 0}

    def _transport(url: str) -> Any:
        calls["n"] += 1
        return feed if feed is not None else _feed()

    provider = FaireconomyNewsProvider(cache_path=tmp_path / "cache.json", transport=_transport)
    provider.calls = calls  # type: ignore[attr-defined]
    return provider


def test_parses_usd_events_only(tmp_path: Path) -> None:
    events = _provider(tmp_path).events()
    titles = [e.title for e in events]
    assert "Non-Farm Payrolls" in titles
    assert "ECB Rate" not in titles  # EUR filtered out


def test_impact_mapping(tmp_path: Path) -> None:
    events = _provider(tmp_path).events()
    by_title = {e.title: e for e in events}
    assert by_title["Non-Farm Payrolls"].impact is NewsImpact.HIGH
    assert by_title["Crude Inventories"].impact is NewsImpact.LOW


def test_time_normalised_to_naive_utc(tmp_path: Path) -> None:
    events = _provider(tmp_path).events()
    nfp = next(e for e in events if e.title == "Non-Farm Payrolls")
    assert nfp.time == datetime(2026, 7, 3, 12, 30)  # 08:30-04:00 -> 12:30 UTC
    assert nfp.time.tzinfo is None


def test_bad_rows_skipped(tmp_path: Path) -> None:
    events = _provider(tmp_path).events()
    assert all(e.title != "Bad row" for e in events)


def test_cache_prevents_refetch(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    provider.events()
    provider.events()
    assert provider.calls["n"] == 1  # type: ignore[attr-defined]


def test_non_array_feed_raises(tmp_path: Path) -> None:
    provider = _provider(tmp_path, feed={"error": "nope"})
    with pytest.raises(DataProviderError, match="JSON array"):
        provider.events()
