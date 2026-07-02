"""Core domain: models, registry, exceptions."""

from xau_ai.core.context import build_context
from xau_ai.core.exceptions import (
    ConfigError,
    DataProviderError,
    NotificationError,
    SkillError,
    XauAiError,
)
from xau_ai.core.models import (
    Candle,
    Direction,
    MarketContext,
    Signal,
    SignalType,
    SkillResult,
    Timeframe,
)
from xau_ai.core.registry import SkillRegistry, registry

__all__ = [
    "Candle",
    "ConfigError",
    "DataProviderError",
    "Direction",
    "MarketContext",
    "NotificationError",
    "Signal",
    "SignalType",
    "SkillError",
    "SkillRegistry",
    "SkillResult",
    "Timeframe",
    "XauAiError",
    "build_context",
    "registry",
]
