"""Tests for notifications (Telegram, owner-only)."""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

import pytest

from xau_ai.core.exceptions import NotificationError
from xau_ai.core.models import Signal, SignalType, Timeframe
from xau_ai.notifications.message import format_signal
from xau_ai.notifications.telegram import TelegramNotifier, _http_post

AS_OF = datetime(2026, 7, 2, 15, 10, 0)
OWNER = 262846950


def _long() -> Signal:
    return Signal(
        signal_type=SignalType.LONG,
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        as_of=AS_OF,
        confidence=0.91,
        entry=3352.6,
        stop_loss=3348.9,
        take_profits=(3357.0, 3363.2),
        risk_reward=2.8,
        reasons=("trend: up",),
        invalidation="close below 3348.90",
        journal_id="J-1",
    )


def _no_trade() -> Signal:
    return Signal(
        signal_type=SignalType.NO_TRADE,
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        as_of=AS_OF,
        confidence=0.4,
    )


class _Capture:
    """Fake transport recording the last call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, url: str, payload: dict[str, Any]) -> None:
        self.calls.append((url, payload))


def test_format_signal_contains_fields() -> None:
    text = format_signal(_long())
    assert "LONG" in text
    assert "3352.60" in text
    assert "1:2.8" in text
    assert "trend: up" in text
    assert "J-1" in text


def test_notify_sends_long_to_owner() -> None:
    transport = _Capture()
    notifier = TelegramNotifier("TOKEN", OWNER, transport=transport)
    assert notifier.notify(_long()) is True
    url, payload = transport.calls[0]
    assert "botTOKEN/sendMessage" in url
    assert payload["chat_id"] == OWNER  # owner-only destination
    assert "LONG" in payload["text"]


def test_notify_skips_no_trade() -> None:
    transport = _Capture()
    notifier = TelegramNotifier("TOKEN", OWNER, transport=transport)
    assert notifier.notify(_no_trade()) is False
    assert transport.calls == []


def test_notify_respects_send_on() -> None:
    transport = _Capture()
    notifier = TelegramNotifier("TOKEN", OWNER, send_on=(SignalType.SHORT,), transport=transport)
    assert notifier.notify(_long()) is False  # only SHORT enabled
    assert transport.calls == []


def test_missing_token_raises() -> None:
    notifier = TelegramNotifier("", OWNER, transport=_Capture())
    with pytest.raises(NotificationError, match="not configured"):
        notifier.notify(_long())


def test_missing_owner_raises() -> None:
    notifier = TelegramNotifier("TOKEN", 0, transport=_Capture())
    with pytest.raises(NotificationError, match="not configured"):
        notifier.notify(_long())


def test_transport_error_is_wrapped() -> None:
    def _boom(url: str, payload: dict[str, Any]) -> None:
        raise NotificationError("boom")

    notifier = TelegramNotifier("TOKEN", OWNER, transport=_boom)
    with pytest.raises(NotificationError, match="boom"):
        notifier.notify(_long())


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_http_post_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_urlopen(request: Any, timeout: int) -> _FakeResponse:
        captured["data"] = request.data
        return _FakeResponse(200)

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    _http_post("https://api.telegram.org/botX/sendMessage", {"chat_id": OWNER})
    assert captured["data"]


def test_http_post_bad_status_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: _FakeResponse(500))
    with pytest.raises(NotificationError, match="HTTP 500"):
        _http_post("https://x", {})


def test_http_post_urlerror_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(request: Any, timeout: int) -> _FakeResponse:
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    with pytest.raises(NotificationError, match="request failed"):
        _http_post("https://x", {})
