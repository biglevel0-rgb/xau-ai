"""Notifier abstraction.

A notifier delivers a signal to some channel. New channels (Slack, e-mail, ...)
implement this Protocol without touching callers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from xau_ai.core.models import Signal


@runtime_checkable
class Notifier(Protocol):
    """Delivers a signal to a channel."""

    def notify(self, signal: Signal) -> bool:
        """Send ``signal``. Return True if delivered, False if skipped by policy."""
        ...
