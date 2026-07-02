"""Weight calibration: tune validator weights against backtest performance."""

from xau_ai.calibration.calibrator import (
    CalibrationResult,
    Calibrator,
    generate_weight_candidates,
    metric_for,
)

__all__ = [
    "CalibrationResult",
    "Calibrator",
    "generate_weight_candidates",
    "metric_for",
]
