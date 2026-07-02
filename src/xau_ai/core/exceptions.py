"""Exception hierarchy for XAU-AI.

A single root (`XauAiError`) lets callers catch everything from this system
without swallowing unrelated errors.
"""

from __future__ import annotations


class XauAiError(Exception):
    """Base class for all XAU-AI errors."""


class ConfigError(XauAiError):
    """Configuration is missing, malformed, or inconsistent."""


class DataProviderError(XauAiError):
    """A market-data provider failed to return usable data."""


class SkillError(XauAiError):
    """A skill failed during analysis or was registered incorrectly."""
