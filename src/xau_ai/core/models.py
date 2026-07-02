"""Core domain models.

Design notes
------------
* Prices are ``float``. Gold analysis (EMAs, ATR, structure) is inherently
  floating-point; monetary rounding happens only at the risk/execution boundary.
* ``Direction`` is what a *skill* votes for (it may be NEUTRAL).
  ``SignalType`` is the *final* verdict and can only be LONG / SHORT / NO_TRADE.
* ``SkillResult.score`` is a calibrated confidence in ``[0, 1]`` — NOT a literal
  statistical probability. Calibration happens against backtest data (Stage 6).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Timeframe(StrEnum):
    """Supported candle timeframes."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    H1 = "H1"
    H4 = "H4"


class Direction(StrEnum):
    """Directional vote emitted by a single skill."""

    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class SignalType(StrEnum):
    """Final, user-facing verdict. No intermediate states allowed."""

    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


class Candle(BaseModel):
    """A single OHLCV bar."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _check_ohlc(self) -> Candle:
        """High must be the max and low the min of the bar."""
        top = max(self.open, self.close)
        bottom = min(self.open, self.close)
        if self.high < top:
            raise ValueError(f"high {self.high} below body top {top}")
        if self.low > bottom:
            raise ValueError(f"low {self.low} above body bottom {bottom}")
        if self.high < self.low:
            raise ValueError(f"high {self.high} below low {self.low}")
        return self


class MarketContext(BaseModel):
    """Everything a skill needs to analyse the market at a point in time.

    Holds one candle series per timeframe. Series are ordered oldest -> newest.
    """

    model_config = ConfigDict(extra="forbid")

    symbol: str
    as_of: datetime
    series: dict[Timeframe, list[Candle]] = Field(default_factory=dict)

    def candles(self, timeframe: Timeframe) -> list[Candle]:
        """Return the series for ``timeframe`` (empty list if absent)."""
        return self.series.get(timeframe, [])

    def latest(self, timeframe: Timeframe) -> Candle | None:
        """Return the most recent candle for ``timeframe``, or ``None``."""
        bars = self.series.get(timeframe)
        return bars[-1] if bars else None


class SkillResult(BaseModel):
    """The output of one skill's independent analysis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skill_name: str
    direction: Direction
    score: float = Field(ge=0.0, le=1.0)
    evidence: tuple[str, ...] = ()
    invalidation: str | None = None
    meta: dict[str, float] = Field(default_factory=dict)


class Signal(BaseModel):
    """The final verdict produced by the signal generator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_type: SignalType
    symbol: str
    timeframe: Timeframe
    as_of: datetime
    confidence: float = Field(ge=0.0, le=1.0)

    entry: float | None = None
    stop_loss: float | None = None
    take_profits: tuple[float, ...] = ()
    risk_reward: float | None = Field(default=None, ge=0.0)

    reasons: tuple[str, ...] = ()
    rejections: tuple[str, ...] = ()
    invalidation: str | None = None
    journal_id: str | None = None

    @model_validator(mode="after")
    def _check_actionable(self) -> Signal:
        """LONG/SHORT must carry entry and stop; NO_TRADE must not."""
        if self.signal_type is SignalType.NO_TRADE:
            if self.entry is not None or self.stop_loss is not None:
                raise ValueError("NO_TRADE must not define entry or stop_loss")
            return self
        if self.entry is None or self.stop_loss is None:
            raise ValueError(f"{self.signal_type.value} requires entry and stop_loss")
        if self.entry == self.stop_loss:
            raise ValueError("entry and stop_loss must differ")
        return self
