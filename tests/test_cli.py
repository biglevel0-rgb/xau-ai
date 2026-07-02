"""Tests for the CLI entry point."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from xau_ai.cli import _maybe_notify, main
from xau_ai.config.settings import NotificationsConfig, TelegramConfig
from xau_ai.core.models import Signal, SignalType, Timeframe

from .conftest import make_settings

_CSV = """timestamp,open,high,low,close,volume
2026-07-02T15:00:00,3350,3352,3349,3351,100
2026-07-02T15:05:00,3351,3353,3350,3352,120
"""


def _seed(tmp_path: Path) -> None:
    (tmp_path / "XAUUSD_M5.csv").write_text(_CSV, encoding="utf-8")


def test_show_data_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(tmp_path)
    code = main(["show-data", "--dir", str(tmp_path), "--tf", "M5", "--count", "5"])
    out = capsys.readouterr().out
    assert code == 0
    assert "XAUUSD" in out
    assert "M5" in out
    assert "3352.00" in out


def test_show_data_missing_file_returns_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["show-data", "--dir", str(tmp_path), "--tf", "M1", "--count", "5"])
    assert code == 1
    assert "error" in capsys.readouterr().out


def test_unknown_timeframe_exits(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="unknown timeframe"):
        main(["show-data", "--dir", str(tmp_path), "--tf", "M7"])


def test_no_command_exits() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_trailing_comma_in_tf_is_ignored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path)
    code = main(["show-data", "--dir", str(tmp_path), "--tf", "M5,", "--count", "5"])
    assert code == 0
    assert "M5" in capsys.readouterr().out


def test_all_empty_tf_exits(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="no timeframes"):
        main(["show-data", "--dir", str(tmp_path), "--tf", " , "])


def _seed_analyze(tmp_path: Path) -> Path:
    header = "timestamp,open,high,low,close,volume\n"
    rows = []
    for i in range(60):
        price = 3300.0 + i * 2
        ts = f"2026-07-02T{13 + i // 12:02d}:{(i % 12) * 5:02d}:00"
        rows.append(f"{ts},{price},{price + 1},{price - 1},{price},100")
    (tmp_path / "XAUUSD_M5.csv").write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    return tmp_path / "config.yaml"


def test_analyze_prints_verdict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = _seed_analyze(tmp_path)
    config_path.write_text(
        """
symbol: XAUUSD
timeframes: [M5]
risk:
  risk_per_trade_pct: 0.5
  min_rr: 2.0
  max_daily_loss_pct: 3.0
  max_weekly_loss_pct: 6.0
validator:
  confidence_threshold: 0.1
  weights: {trend: 1.0}
  required_confirmations: [trend]
news:
  block_minutes_before: 15
  block_minutes_after: 15
""",
        encoding="utf-8",
    )
    code = main(["analyze", "--dir", str(tmp_path), "--tf", "M5", "--config", str(config_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "VERDICT" in out


def test_analyze_missing_config_returns_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_analyze(tmp_path)
    code = main(["analyze", "--dir", str(tmp_path), "--tf", "M5", "--config", "nope.yaml"])
    assert code == 1
    assert "error" in capsys.readouterr().out


def test_analyze_twelvedata_without_key_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TWELVEDATA_API_KEY", raising=False)
    config = _seed_analyze(tmp_path)
    config.write_text(_PERMISSIVE_CONFIG, encoding="utf-8")
    code = main(["analyze", "--provider", "twelvedata", "--tf", "M5", "--config", str(config)])
    assert code == 1
    assert "API key" in capsys.readouterr().out


def _write_bars(path: Path, symbol: str, tf: str, base: float = 3300.0) -> None:
    header = "timestamp,open,high,low,close,volume\n"
    rows = []
    for i in range(60):
        price = base + i * 2
        ts = f"2026-07-02T{13 + i // 12:02d}:{(i % 12) * 5:02d}:00"
        rows.append(f"{ts},{price},{price + 1},{price - 1},{price},100")
    (path / f"{symbol}_{tf}.csv").write_text(header + "\n".join(rows) + "\n", encoding="utf-8")


def test_analyze_multitimeframe_with_related(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_bars(tmp_path, "XAUUSD", "M5")
    _write_bars(tmp_path, "XAUUSD", "M15")
    _write_bars(tmp_path, "DXY", "M5", base=100.0)  # correlated instrument
    config = tmp_path / "config.yaml"
    config.write_text(
        """
symbol: XAUUSD
timeframes: [M5, M15]
related_symbols: [DXY]
risk:
  risk_per_trade_pct: 0.5
  min_rr: 2.0
  max_daily_loss_pct: 3.0
  max_weekly_loss_pct: 6.0
validator:
  confidence_threshold: 0.1
  weights: {trend: 1.0}
  required_confirmations: [trend]
news:
  block_minutes_before: 15
  block_minutes_after: 15
""",
        encoding="utf-8",
    )
    code = main(["analyze", "--dir", str(tmp_path), "--tf", "M5", "--config", str(config)])
    out = capsys.readouterr().out
    assert code == 0
    assert "VERDICT" in out


_PERMISSIVE_CONFIG = """
symbol: XAUUSD
timeframes: [M5]
risk:
  risk_per_trade_pct: 0.5
  min_rr: 2.0
  max_daily_loss_pct: 3.0
  max_weekly_loss_pct: 6.0
validator:
  confidence_threshold: 0.1
  weights: {trend: 1.0}
  required_confirmations: [trend]
news:
  block_minutes_before: 15
  block_minutes_after: 15
"""


def test_backtest_prints_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = _seed_analyze(tmp_path)
    config_path.write_text(_PERMISSIVE_CONFIG, encoding="utf-8")
    code = main(
        [
            "backtest",
            "--dir",
            str(tmp_path),
            "--tf",
            "M5",
            "--warmup",
            "55",
            "--config",
            str(config_path),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "BACKTEST REPORT" in out


def test_backtest_missing_file_returns_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(_PERMISSIVE_CONFIG, encoding="utf-8")
    code = main(["backtest", "--dir", str(tmp_path), "--tf", "M5", "--config", str(config_path)])
    assert code == 1
    assert "error" in capsys.readouterr().out


def test_calibrate_prints_best_weights(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = _seed_analyze(tmp_path)
    config_path.write_text(_PERMISSIVE_CONFIG, encoding="utf-8")
    code = main(
        [
            "calibrate",
            "--dir",
            str(tmp_path),
            "--tf",
            "M5",
            "--warmup",
            "55",
            "--config",
            str(config_path),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "CALIBRATION" in out
    assert "Best weights" in out


def test_calibrate_missing_file_returns_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(_PERMISSIVE_CONFIG, encoding="utf-8")
    code = main(["calibrate", "--dir", str(tmp_path), "--tf", "M5", "--config", str(config_path)])
    assert code == 1
    assert "error" in capsys.readouterr().out


def _write_m1_bars(path: Path, symbol: str = "XAUUSD", n: int = 400) -> None:
    header = "timestamp,open,high,low,close,volume\n"
    rows = []
    for i in range(n):
        price = 3300.0 + i * 0.5
        ts = f"2026-07-02T{7 + i // 60:02d}:{i % 60:02d}:00"
        rows.append(f"{ts},{price},{price + 0.5},{price - 0.5},{price},50")
    (path / f"{symbol}_M1.csv").write_text(header + "\n".join(rows) + "\n", encoding="utf-8")


def test_forecast_prints_bias(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_m1_bars(tmp_path)
    config = tmp_path / "config.yaml"
    config.write_text(_PERMISSIVE_CONFIG, encoding="utf-8")
    code = main(["forecast", "--dir", str(tmp_path), "--count", "400", "--config", str(config)])
    out = capsys.readouterr().out
    assert code == 0
    assert "forecast" in out
    assert ("LONG" in out) or ("SHORT" in out) or ("FLAT" in out)
    assert "not a vetted trade signal" in out


def test_forecast_strong_alert_at_threshold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Permissive config: threshold 0.1, only trend weighted -> a steady uptrend
    # easily clears the threshold and must produce the STRONG alert line.
    _write_m1_bars(tmp_path)
    config = tmp_path / "config.yaml"
    config.write_text(_PERMISSIVE_CONFIG, encoding="utf-8")
    code = main(["forecast", "--dir", str(tmp_path), "--count", "400", "--config", str(config)])
    out = capsys.readouterr().out
    assert code == 0
    assert "STRONG" in out


def test_forecast_no_alert_when_flat(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Flat market -> NEUTRAL bias -> never a STRONG alert regardless of threshold.
    header = "timestamp,open,high,low,close,volume\n"
    rows = [
        f"2026-07-02T{7 + i // 60:02d}:{i % 60:02d}:00,3300,3300.5,3299.5,3300,50"
        for i in range(400)
    ]
    (tmp_path / "XAUUSD_M1.csv").write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(_PERMISSIVE_CONFIG, encoding="utf-8")
    code = main(["forecast", "--dir", str(tmp_path), "--count", "400", "--config", str(config)])
    out = capsys.readouterr().out
    assert code == 0
    assert "STRONG" not in out
    assert "FLAT" in out


def test_forecast_with_related_symbol_activates_correlation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_m1_bars(tmp_path)  # rising gold M1
    _write_bars(tmp_path, "EURUSD", "M5", base=1.10)  # rising EURUSD -> positive corr -> LONG
    config = tmp_path / "config.yaml"
    config.write_text(
        _PERMISSIVE_CONFIG.replace(
            "weights: {trend: 1.0}", "weights: {trend: 0.5, correlation: 0.5}"
        )
        + "related_symbols: [EURUSD]\n",
        encoding="utf-8",
    )
    code = main(["forecast", "--dir", str(tmp_path), "--count", "400", "--config", str(config)])
    out = capsys.readouterr().out
    assert code == 0
    assert "correlation" in out  # correlation skill voted and is listed


def test_forecast_missing_related_is_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_m1_bars(tmp_path)  # no EURUSD file present
    config = tmp_path / "config.yaml"
    config.write_text(_PERMISSIVE_CONFIG + "related_symbols: [EURUSD]\n", encoding="utf-8")
    code = main(["forecast", "--dir", str(tmp_path), "--count", "400", "--config", str(config)])
    assert code == 0  # missing related must not break the forecast


def test_forecast_missing_data_returns_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(_PERMISSIVE_CONFIG, encoding="utf-8")
    code = main(["forecast", "--dir", str(tmp_path), "--config", str(config)])
    assert code == 1
    assert "error" in capsys.readouterr().out


AS_OF = datetime(2026, 7, 2, 15, 0, 0)


def _no_trade_signal() -> Signal:
    return Signal(
        signal_type=SignalType.NO_TRADE,
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        as_of=AS_OF,
        confidence=0.4,
    )


def _long_signal() -> Signal:
    return Signal(
        signal_type=SignalType.LONG,
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        as_of=AS_OF,
        confidence=0.9,
        entry=3352.6,
        stop_loss=3348.9,
        risk_reward=2.8,
    )


def test_maybe_notify_disabled(capsys: pytest.CaptureFixture[str]) -> None:
    settings = make_settings().model_copy(
        update={"notifications": NotificationsConfig(telegram=TelegramConfig(enabled=False))}
    )
    _maybe_notify(settings, _long_signal())
    assert "disabled" in capsys.readouterr().out


def test_maybe_notify_skips_no_trade(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    _maybe_notify(make_settings(), _no_trade_signal())  # NO_TRADE -> skipped, no token needed
    assert "skipped" in capsys.readouterr().out


def test_maybe_notify_reports_error_without_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("xau_ai.config.settings.Secrets", lambda: _NoSecrets())
    _maybe_notify(make_settings(), _long_signal())
    assert "notify error" in capsys.readouterr().out


class _NoSecrets:
    telegram_bot_token = ""
    telegram_owner_chat_id = 0
