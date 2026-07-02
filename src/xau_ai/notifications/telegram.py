"""Telegram notifier (owner-only).

Delivers LONG/SHORT signals to a single owner chat via the Telegram Bot API.
It is *send-only* and never reads incoming messages, so no one but the owner can
ever receive anything — the owner chat id is the only destination.

The HTTP call is injected as ``transport`` so tests never touch the network.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any

from xau_ai.core.exceptions import NotificationError
from xau_ai.core.models import Signal, SignalType
from xau_ai.notifications.message import format_signal

Transport = Callable[[str, dict[str, Any]], None]

_DEFAULT_SEND_ON: tuple[SignalType, ...] = (SignalType.LONG, SignalType.SHORT)


def _http_post(url: str, payload: dict[str, Any]) -> None:
    """Default transport: POST ``payload`` as JSON to ``url``."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise NotificationError(f"Telegram HTTP {response.status}")
    except urllib.error.URLError as exc:
        raise NotificationError(f"Telegram request failed: {exc}") from exc


class TelegramNotifier:
    """Send signals to the owner's Telegram chat."""

    def __init__(
        self,
        bot_token: str,
        owner_chat_id: int,
        send_on: Sequence[SignalType] = _DEFAULT_SEND_ON,
        transport: Transport | None = None,
    ) -> None:
        self._token = bot_token
        self._owner_chat_id = owner_chat_id
        self._send_on = tuple(send_on)
        self._transport = transport or _http_post

    def notify(self, signal: Signal) -> bool:
        """Send ``signal`` to the owner if its type is enabled; else skip."""
        if signal.signal_type not in self._send_on:
            return False
        if not self._token or self._owner_chat_id == 0:
            raise NotificationError("Telegram bot token / owner chat id not configured")

        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": self._owner_chat_id,  # owner-only: the sole destination
            "text": format_signal(signal),
            "disable_web_page_preview": True,
        }
        self._transport(url, payload)
        return True
