"""Skill registry.

New skills register themselves via the ``@registry.register`` decorator, so the
orchestrator can discover them without importing each one explicitly
(Open/Closed principle). Importing a skill module is enough to register it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xau_ai.core.exceptions import SkillError

if TYPE_CHECKING:
    from xau_ai.skills.base import BaseSkill


class SkillRegistry:
    """Registry mapping a skill's unique name to its class."""

    def __init__(self) -> None:
        self._skills: dict[str, type[BaseSkill]] = {}

    def register(self, skill_cls: type[BaseSkill]) -> type[BaseSkill]:
        """Register ``skill_cls``. Usable as a decorator. Names must be unique."""
        name = skill_cls.name
        if not name:
            raise SkillError(f"{skill_cls.__name__} has an empty skill name")
        if name in self._skills:
            raise SkillError(f"duplicate skill name: {name!r}")
        self._skills[name] = skill_cls
        return skill_cls

    def get(self, name: str) -> type[BaseSkill]:
        """Return the skill class registered under ``name``."""
        try:
            return self._skills[name]
        except KeyError as exc:
            raise SkillError(f"unknown skill: {name!r}") from exc

    def all(self) -> tuple[type[BaseSkill], ...]:
        """Return all registered skill classes, ordered by name."""
        return tuple(self._skills[n] for n in sorted(self._skills))

    def names(self) -> tuple[str, ...]:
        """Return all registered skill names, sorted."""
        return tuple(sorted(self._skills))

    def clear(self) -> None:
        """Remove all registrations (used by tests)."""
        self._skills.clear()


registry = SkillRegistry()
