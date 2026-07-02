"""Tests for the news module (events, providers, filter skill)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from xau_ai.core.exceptions import DataProviderError
from xau_ai.core.models import Direction, MarketContext, Timeframe
from xau_ai.data.news.events import NewsEvent, NewsImpact
from xau_ai.data.news.providers import CsvNewsProvider, StaticNewsProvider
from xau_ai.skills.news import NewsFilterSkill

EVENT_TIME = datetime(2026, 7, 2, 15, 0, 0)


def _ctx(as_of: datetime) -> MarketContext:
    return MarketContext(symbol="XAUUSD", as_of=as_of, series={Timeframe.M5: []})


def _event(impact: NewsImpact = NewsImpact.HIGH) -> NewsEvent:
    return NewsEvent(time=EVENT_TIME, title="NFP", impact=impact, currency="USD")


def test_impact_rank_ordering() -> None:
    assert NewsImpact.HIGH.rank > NewsImpact.MEDIUM.rank > NewsImpact.LOW.rank


def test_vetoes_inside_window() -> None:
    skill = NewsFilterSkill(StaticNewsProvider([_event()]))
    result = skill.analyze(_ctx(datetime(2026, 7, 2, 15, 10, 0)))  # 10 min after
    assert result.veto is True
    assert result.direction is Direction.NEUTRAL
    assert "NFP" in result.evidence[0]


def test_vetoes_before_event() -> None:
    skill = NewsFilterSkill(StaticNewsProvider([_event()]))
    result = skill.analyze(_ctx(datetime(2026, 7, 2, 14, 50, 0)))  # 10 min before
    assert result.veto is True


def test_no_veto_outside_window() -> None:
    skill = NewsFilterSkill(StaticNewsProvider([_event()]))
    result = skill.analyze(_ctx(datetime(2026, 7, 2, 16, 0, 0)))  # 1h after
    assert result.veto is False
    assert "no high-impact" in result.evidence[0]


def test_low_impact_ignored() -> None:
    skill = NewsFilterSkill(StaticNewsProvider([_event(NewsImpact.MEDIUM)]))
    result = skill.analyze(_ctx(datetime(2026, 7, 2, 15, 5, 0)))
    assert result.veto is False


def test_empty_provider_never_vetoes() -> None:
    result = NewsFilterSkill().analyze(_ctx(EVENT_TIME))
    assert result.veto is False


def test_calendar_outage_abstains_not_crashes() -> None:
    class _Broken:
        def events(self) -> list[NewsEvent]:
            raise DataProviderError("HTTP 403")

    result = NewsFilterSkill(_Broken()).analyze(_ctx(EVENT_TIME))
    assert result.veto is False
    assert result.direction is Direction.NEUTRAL
    assert "unavailable" in result.evidence[0]


def test_csv_provider_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "news.csv"
    path.write_text(
        "timestamp,impact,title,currency\n2026-07-02T15:00:00,high,NFP,USD\n",
        encoding="utf-8",
    )
    events = CsvNewsProvider(path).events()
    assert len(events) == 1
    assert events[0].impact is NewsImpact.HIGH


def test_csv_provider_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DataProviderError, match="not found"):
        CsvNewsProvider(tmp_path / "nope.csv").events()


def test_csv_provider_missing_column(tmp_path: Path) -> None:
    path = tmp_path / "news.csv"
    path.write_text("timestamp,title\n2026-07-02T15:00:00,NFP\n", encoding="utf-8")
    with pytest.raises(DataProviderError, match="missing columns"):
        CsvNewsProvider(path).events()


def test_csv_provider_bad_row(tmp_path: Path) -> None:
    path = tmp_path / "news.csv"
    path.write_text("timestamp,impact,title\nnot-a-date,high,NFP\n", encoding="utf-8")
    with pytest.raises(DataProviderError, match="bad event"):
        CsvNewsProvider(path).events()


def test_skill_is_registered() -> None:
    from xau_ai.core.registry import registry

    assert registry.get("news") is NewsFilterSkill
