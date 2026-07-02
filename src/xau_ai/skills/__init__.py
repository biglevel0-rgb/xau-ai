"""Independent analytical skills.

Each skill subclasses :class:`~xau_ai.skills.base.BaseSkill`, declares a unique
``name``, and implements ``analyze`` to return a
:class:`~xau_ai.core.models.SkillResult`.
"""

from xau_ai.skills.base import BaseSkill

__all__ = ["BaseSkill"]
