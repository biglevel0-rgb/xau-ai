"""Independent analytical skills.

Each skill subclasses :class:`~xau_ai.skills.base.BaseSkill`, declares a unique
``name``, and implements ``analyze`` to return a
:class:`~xau_ai.core.models.SkillResult`.

Importing this package registers all built-in skills with the global
:data:`~xau_ai.core.registry.registry` (via each skill's ``@registry.register``).
"""

from xau_ai.skills.base import BaseSkill
from xau_ai.skills.market_structure import MarketStructureSkill
from xau_ai.skills.sessions import SessionSkill
from xau_ai.skills.trend import TrendSkill

__all__ = [
    "BaseSkill",
    "MarketStructureSkill",
    "SessionSkill",
    "TrendSkill",
]
