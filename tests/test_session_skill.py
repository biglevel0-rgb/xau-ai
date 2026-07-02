"""Tests for the session skill."""

from __future__ import annotations

from datetime import UTC, datetime

from xau_ai.core.models import Direction, MarketContext
from xau_ai.skills.sessions import SessionSkill


def _ctx_at(hour: int, *, tz: bool = False) -> MarketContext:
    tzinfo = UTC if tz else None
    return MarketContext(
        symbol="XAUUSD",
        as_of=datetime(2026, 7, 2, hour, 0, 0, tzinfo=tzinfo),
    )


def test_direction_is_always_neutral() -> None:
    result = SessionSkill().analyze(_ctx_at(13))
    assert result.direction is Direction.NEUTRAL


def test_overlap_is_high_score_and_kill_zone() -> None:
    result = SessionSkill().analyze(_ctx_at(13))
    assert result.score >= 0.9
    assert any("Overlap" in e for e in result.evidence)
    assert any("kill zone" in e for e in result.evidence)


def test_london_kill_zone() -> None:
    result = SessionSkill().analyze(_ctx_at(9))
    assert any("London" in e for e in result.evidence)
    assert result.score >= 0.85


def test_asia_is_low_score() -> None:
    result = SessionSkill().analyze(_ctx_at(3))
    assert result.score < 0.5
    assert any("Asia" in e for e in result.evidence)


def test_off_hours_is_lowest() -> None:
    # 16:00-21:59 is New York; use a gap hour that is neither London nor NY nor Asia.
    result = SessionSkill().analyze(_ctx_at(21))
    assert any("Off-hours" in e for e in result.evidence)


def test_late_night_is_asia() -> None:
    result = SessionSkill().analyze(_ctx_at(23))
    assert any("Asia" in e for e in result.evidence)
    assert result.score < 0.5


def test_timezone_aware_is_converted_to_utc() -> None:
    result = SessionSkill().analyze(_ctx_at(13, tz=True))
    assert any("Overlap" in e for e in result.evidence)


def test_skill_is_registered() -> None:
    from xau_ai.core.registry import registry

    assert registry.get("session") is SessionSkill
