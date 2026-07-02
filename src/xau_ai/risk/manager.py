"""Risk manager.

Turns a direction + current price + ATR into a concrete trade plan:

* **Stop** is placed ``stop_atr_mult * ATR`` away from entry.
* **Take-profits** sit at the configured R multiples of that stop distance, so the
  reward:risk to TP ``n`` equals ``tp_rr_multiples[n]``.
* **Position size** risks exactly ``risk_per_trade_pct`` of the account balance,
  rounded *down* to the broker lot step (never round risk up).
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, model_validator

from xau_ai.config.settings import RiskConfig
from xau_ai.core.exceptions import XauAiError
from xau_ai.core.models import Direction


class TradePlan(BaseModel):
    """A fully specified trade (levels + size)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    direction: Direction
    entry: float
    stop_loss: float
    take_profits: tuple[float, ...]
    risk_reward: float = Field(ge=0.0)
    lots: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _check(self) -> TradePlan:
        if self.direction is Direction.NEUTRAL:
            raise ValueError("a trade plan requires a directional signal")
        if self.entry == self.stop_loss:
            raise ValueError("entry and stop_loss must differ")
        return self


class RiskManager:
    """Build trade plans from a :class:`RiskConfig`."""

    def __init__(self, config: RiskConfig) -> None:
        self._config = config

    def position_size(self, entry: float, stop_loss: float) -> float:
        """Lots such that hitting the stop loses ``risk_per_trade_pct`` of balance."""
        stop_distance = abs(entry - stop_loss)
        if stop_distance <= 0:
            raise XauAiError("stop distance must be positive to size a position")
        risk_amount = self._config.account_balance * self._config.risk_per_trade_pct / 100.0
        loss_per_lot = stop_distance * self._config.contract_size
        raw_lots = risk_amount / loss_per_lot
        steps = math.floor(raw_lots / self._config.lot_step)
        return round(steps * self._config.lot_step, 8)

    def build_plan(self, direction: Direction, entry: float, atr_value: float) -> TradePlan:
        """Construct a :class:`TradePlan` for ``direction`` at ``entry`` given ``atr_value``."""
        if direction is Direction.NEUTRAL:
            raise XauAiError("cannot build a plan for a NEUTRAL direction")
        if atr_value <= 0:
            raise XauAiError("ATR must be positive to build a plan")

        stop_distance = atr_value * self._config.stop_atr_mult
        multiples = self._config.tp_rr_multiples
        if direction is Direction.LONG:
            stop_loss = entry - stop_distance
            take_profits = tuple(entry + m * stop_distance for m in multiples)
        else:
            stop_loss = entry + stop_distance
            take_profits = tuple(entry - m * stop_distance for m in multiples)

        risk_reward = multiples[self._config.primary_tp_index]
        lots = self.position_size(entry, stop_loss)
        return TradePlan(
            direction=direction,
            entry=entry,
            stop_loss=stop_loss,
            take_profits=take_profits,
            risk_reward=risk_reward,
            lots=lots,
        )
