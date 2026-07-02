"""Tests for the settings loader."""

from __future__ import annotations

from pathlib import Path

import pydantic
import pytest

from xau_ai.config.settings import Settings, TelegramConfig, ValidatorConfig, load_settings
from xau_ai.core.exceptions import ConfigError
from xau_ai.core.models import SignalType, Timeframe

REPO_ROOT = Path(__file__).resolve().parents[1]

_VALID_YAML = """
symbol: XAUUSD
timeframes: [M1, M5]
risk:
  risk_per_trade_pct: 0.5
  min_rr: 2.0
  max_daily_loss_pct: 3.0
  max_weekly_loss_pct: 6.0
validator:
  confidence_threshold: 0.85
  weights: {trend: 0.5, liquidity: 0.5}
  hard_conditions: [min_rr]
news:
  block_minutes_before: 15
  block_minutes_after: 15
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "settings.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_valid_settings(tmp_path: Path) -> None:
    settings = load_settings(_write(tmp_path, _VALID_YAML))
    assert settings.symbol == "XAUUSD"
    assert settings.timeframes == (Timeframe.M1, Timeframe.M5)
    assert settings.validator.confidence_threshold == 0.85


def test_repo_settings_file_is_valid() -> None:
    settings = load_settings(REPO_ROOT / "config" / "settings.yaml")
    assert isinstance(settings, Settings)
    assert SignalType.NO_TRADE not in settings.notifications.telegram.send_on


def test_missing_file_raises() -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_settings("/nonexistent/settings.yaml")


def test_weights_not_summing_to_one_rejected(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace("{trend: 0.5, liquidity: 0.5}", "{trend: 0.3, liquidity: 0.3}")
    with pytest.raises(ConfigError, match="sum"):
        load_settings(_write(tmp_path, bad))


def test_unknown_field_rejected(tmp_path: Path) -> None:
    bad = _VALID_YAML + "unexpected_key: 1\n"
    with pytest.raises(ConfigError):
        load_settings(_write(tmp_path, bad))


def test_non_mapping_root_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="mapping"):
        load_settings(_write(tmp_path, "- just\n- a\n- list\n"))


def test_invalid_yaml_syntax_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_settings(_write(tmp_path, "symbol: [unclosed\n"))


def test_empty_weights_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="must not be empty"):
        ValidatorConfig(confidence_threshold=0.85, weights={})


def test_negative_weight_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="non-negative"):
        ValidatorConfig(confidence_threshold=0.85, weights={"a": 1.2, "b": -0.2})


def test_telegram_send_on_no_trade_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="NO_TRADE"):
        TelegramConfig(send_on=(SignalType.NO_TRADE,))
