"""Tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path

import pytest

from xau_ai.cli import main

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
