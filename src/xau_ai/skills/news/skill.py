"""News filter skill.

A protective stop, not a directional call: if a sufficiently important event
falls inside the blackout window around the current time, the skill *vetoes* the
trade (forcing NO_TRADE). Otherwise it abstains (NEUTRAL) and confirms "no news".

By default it uses an empty provider (never blocks); a configured provider is
injected for live use.
"""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

from xau_ai.core.models import Direction, MarketContext, SkillResult
from xau_ai.core.registry import registry
from xau_ai.data.news.events import NewsEvent, NewsImpact
from xau_ai.data.news.providers import NewsProvider, StaticNewsProvider
from xau_ai.skills.base import BaseSkill


@registry.register
class NewsFilterSkill(BaseSkill):
    """Veto trading inside the blackout window around high-impact events."""

    name: ClassVar[str] = "news"

    def __init__(
        self,
        provider: NewsProvider | None = None,
        block_minutes_before: int = 15,
        block_minutes_after: int = 15,
        min_impact: NewsImpact = NewsImpact.HIGH,
    ) -> None:
        self._provider = provider or StaticNewsProvider()
        self._before = timedelta(minutes=block_minutes_before)
        self._after = timedelta(minutes=block_minutes_after)
        self._min_rank = min_impact.rank

    def _blocking_event(self, ctx: MarketContext) -> NewsEvent | None:
        as_of = ctx.as_of
        for event in self._provider.events():
            if event.impact.rank < self._min_rank:
                continue
            if event.time - self._before <= as_of <= event.time + self._after:
                return event
        return None

    def analyze(self, ctx: MarketContext) -> SkillResult:
        event = self._blocking_event(ctx)
        if event is not None:
            return SkillResult(
                skill_name=self.name,
                direction=Direction.NEUTRAL,
                score=0.0,
                evidence=(f"{event.impact.value}-impact news: {event.title}",),
                veto=True,
            )
        return SkillResult(
            skill_name=self.name,
            direction=Direction.NEUTRAL,
            score=1.0,
            evidence=("no high-impact news in window",),
        )
