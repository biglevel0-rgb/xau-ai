"""Application settings.

Two sources, kept strictly separate:

* **Non-secret settings** come from ``config/settings.yaml`` -> :class:`Settings`.
* **Secrets** (tokens/keys) come from the environment / ``.env`` -> :class:`Secrets`.

This split guarantees secrets never live in the YAML that gets committed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from xau_ai.core.exceptions import ConfigError
from xau_ai.core.models import SignalType, Timeframe


class RiskConfig(BaseModel):
    """Risk-management parameters."""

    model_config = ConfigDict(extra="forbid")

    risk_per_trade_pct: float = Field(gt=0.0, le=100.0)
    min_rr: float = Field(gt=0.0)
    max_daily_loss_pct: float = Field(gt=0.0, le=100.0)
    max_weekly_loss_pct: float = Field(gt=0.0, le=100.0)

    # Trade-plan construction (sensible defaults; overridable in YAML).
    stop_atr_mult: float = Field(default=1.5, gt=0.0)
    tp_rr_multiples: tuple[float, ...] = (1.0, 2.0, 3.0)
    primary_tp_index: int = Field(default=1, ge=0)
    atr_period: int = Field(default=14, gt=0)
    account_balance: float = Field(default=10_000.0, gt=0.0)
    contract_size: float = Field(default=100.0, gt=0.0)
    lot_step: float = Field(default=0.01, gt=0.0)

    @model_validator(mode="after")
    def _check_tp(self) -> RiskConfig:
        if not self.tp_rr_multiples:
            raise ValueError("tp_rr_multiples must not be empty")
        if any(m <= 0 for m in self.tp_rr_multiples):
            raise ValueError("tp_rr_multiples must be positive")
        if self.primary_tp_index >= len(self.tp_rr_multiples):
            raise ValueError("primary_tp_index out of range for tp_rr_multiples")
        return self


class ValidatorConfig(BaseModel):
    """Signal-validation parameters."""

    model_config = ConfigDict(extra="forbid")

    confidence_threshold: float = Field(ge=0.0, le=1.0)
    weights: dict[str, float]
    hard_conditions: tuple[str, ...] = ()
    # Skills that MUST vote the signal direction, else NO_TRADE.
    required_confirmations: tuple[str, ...] = ()

    @field_validator("weights")
    @classmethod
    def _weights_valid(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            raise ValueError("weights must not be empty")
        if any(w < 0 for w in value.values()):
            raise ValueError("weights must be non-negative")
        total = sum(value.values())
        if not 0.99 <= total <= 1.01:
            raise ValueError(f"weights must sum to ~1.0, got {total:.3f}")
        return value


class SessionsConfig(BaseModel):
    """Which trading sessions are allowed."""

    model_config = ConfigDict(extra="forbid")

    trade_only_in: tuple[str, ...] = ()


class NewsConfig(BaseModel):
    """News-blackout window around high-impact events."""

    model_config = ConfigDict(extra="forbid")

    block_minutes_before: int = Field(ge=0)
    block_minutes_after: int = Field(ge=0)


class TelegramConfig(BaseModel):
    """Telegram notification settings (non-secret; token lives in .env)."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    send_on: tuple[SignalType, ...] = (SignalType.LONG, SignalType.SHORT)
    include_chart: bool = False

    @field_validator("send_on")
    @classmethod
    def _no_no_trade(cls, value: tuple[SignalType, ...]) -> tuple[SignalType, ...]:
        if SignalType.NO_TRADE in value:
            raise ValueError("NO_TRADE cannot be a notification trigger")
        return value


class NotificationsConfig(BaseModel):
    """Container for notification channels."""

    model_config = ConfigDict(extra="forbid")

    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


class Settings(BaseModel):
    """Root, non-secret application settings loaded from YAML."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    timeframes: tuple[Timeframe, ...]
    risk: RiskConfig
    validator: ValidatorConfig
    sessions: SessionsConfig = Field(default_factory=SessionsConfig)
    news: NewsConfig
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)


class Secrets(BaseSettings):
    """Secrets loaded from environment / ``.env``. Never serialised to disk."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = ""
    telegram_owner_chat_id: int = 0
    oanda_api_token: str = ""
    oanda_account_id: str = ""
    twelvedata_api_key: str = ""
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""


def load_settings(path: str | Path) -> Settings:
    """Load and validate :class:`Settings` from a YAML file."""
    file_path = Path(path)
    if not file_path.is_file():
        raise ConfigError(f"settings file not found: {file_path}")
    try:
        raw: Any = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {file_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"settings root must be a mapping, got {type(raw).__name__}")
    try:
        return Settings.model_validate(raw)
    except ValueError as exc:
        raise ConfigError(f"invalid settings in {file_path}: {exc}") from exc
