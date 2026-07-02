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
