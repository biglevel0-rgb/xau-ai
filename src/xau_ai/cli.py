"""Command-line entry point for XAU-AI.

Usage::

    xau show-data --dir ./data_cache --symbol XAUUSD --tf M1,M5 --count 5
    xau analyze   --dir ./data_cache --symbol XAUUSD --tf M5 --config config/settings.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from xau_ai.config.settings import load_settings
from xau_ai.core.context import build_context
from xau_ai.core.exceptions import XauAiError
from xau_ai.core.models import MarketContext, Signal, SignalType, Timeframe
from xau_ai.data.csv_provider import CsvDataProvider


def _parse_timeframes(raw: str) -> list[Timeframe]:
    result: list[Timeframe] = []
    for token in raw.split(","):
        name = token.strip().upper()
        if not name:
            continue
        try:
            result.append(Timeframe(name))
        except ValueError as exc:
            valid = ", ".join(tf.value for tf in Timeframe)
            raise SystemExit(f"unknown timeframe {name!r}; valid: {valid}") from exc
    if not result:
        raise SystemExit("no timeframes given")
    return result


def _print_context(ctx: MarketContext) -> None:
    print(f"Symbol: {ctx.symbol}   as_of: {ctx.as_of.isoformat()}")
    for timeframe in Timeframe:
        candles = ctx.candles(timeframe)
        if not candles:
            continue
        last = candles[-1]
        print(
            f"  {timeframe.value:>3}: {len(candles):>4} bars  "
            f"last close={last.close:.2f} @ {last.timestamp.isoformat()}"
        )


def _cmd_show_data(args: argparse.Namespace) -> int:
    provider = CsvDataProvider(Path(args.dir))
    timeframes = _parse_timeframes(args.tf)
    try:
        ctx = build_context(provider, args.symbol, timeframes, args.count)
    except XauAiError as exc:
        print(f"error: {exc}")
        return 1
    _print_context(ctx)
    return 0


_SIGNAL_ICON = {SignalType.LONG: "🟢", SignalType.SHORT: "🔴", SignalType.NO_TRADE: "⛔"}


def _print_signal(signal: Signal) -> None:
    icon = _SIGNAL_ICON[signal.signal_type]
    print("=" * 44)
    print(f"  XAU-AI • {signal.symbol} • {signal.timeframe.value} • {signal.as_of.isoformat()}")
    print("=" * 44)
    print(f"  VERDICT: {icon} {signal.signal_type.value}")
    print(f"  Confidence: {signal.confidence:.0%}")
    if signal.signal_type is not SignalType.NO_TRADE:
        print(f"  Entry: {signal.entry:.2f}   SL: {signal.stop_loss:.2f}")
        tps = "  ".join(f"TP{i}:{tp:.2f}" for i, tp in enumerate(signal.take_profits, 1))
        print(f"  {tps}")
        rr = signal.risk_reward if signal.risk_reward is not None else 0.0
        print(f"  RR: 1:{rr:.1f}")
    if signal.reasons:
        print("  Reasons:")
        for reason in signal.reasons:
            print(f"    ✔ {reason}")
    if signal.rejections:
        print("  Rejected:")
        for rejection in signal.rejections:
            print(f"    ✗ {rejection}")
    if signal.invalidation:
        print(f"  Invalidation: {signal.invalidation}")
    print("=" * 44)


def _cmd_analyze(args: argparse.Namespace) -> int:
    # Imported here so `show-data` stays fast and free of skill registration.
    from xau_ai.core.orchestrator import Orchestrator

    try:
        settings = load_settings(args.config)
        timeframe = _parse_timeframes(args.tf)[0]
        provider = CsvDataProvider(Path(args.dir))
        ctx = build_context(provider, args.symbol, [timeframe], args.count)
        signal = Orchestrator(settings, timeframe).analyze(ctx)
    except XauAiError as exc:
        print(f"error: {exc}")
        return 1
    _print_signal(signal)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xau", description="XAU-AI command line.")
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("show-data", help="load and summarise candles from CSV")
    show.add_argument("--dir", required=True, help="directory with <SYMBOL>_<TF>.csv files")
    show.add_argument("--symbol", default="XAUUSD")
    show.add_argument("--tf", default="M1,M5", help="comma-separated timeframes")
    show.add_argument("--count", type=int, default=100)
    show.set_defaults(func=_cmd_show_data)

    analyze = sub.add_parser("analyze", help="run all skills and emit a signal")
    analyze.add_argument("--dir", required=True, help="directory with <SYMBOL>_<TF>.csv files")
    analyze.add_argument("--symbol", default="XAUUSD")
    analyze.add_argument("--tf", default="M5", help="signal timeframe (single)")
    analyze.add_argument("--count", type=int, default=300)
    analyze.add_argument("--config", default="config/settings.yaml")
    analyze.set_defaults(func=_cmd_analyze)
    return parser


def _force_utf8_output() -> None:
    """Make stdout/stderr UTF-8 so decorative glyphs never crash a legacy console."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    """Entry point registered as the ``xau`` console script."""
    _force_utf8_output()
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = args.func
    exit_code: int = handler(args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
