"""Command-line entry point for XAU-AI.

Stage 1 exposes data inspection. Analysis/signal commands arrive in later stages.

Usage::

    xau show-data --dir ./data_cache --symbol XAUUSD --tf M1,M5 --count 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

from xau_ai.core.context import build_context
from xau_ai.core.exceptions import XauAiError
from xau_ai.core.models import MarketContext, Timeframe
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xau", description="XAU-AI command line.")
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("show-data", help="load and summarise candles from CSV")
    show.add_argument("--dir", required=True, help="directory with <SYMBOL>_<TF>.csv files")
    show.add_argument("--symbol", default="XAUUSD")
    show.add_argument("--tf", default="M1,M5", help="comma-separated timeframes")
    show.add_argument("--count", type=int, default=100)
    show.set_defaults(func=_cmd_show_data)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point registered as the ``xau`` console script."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = args.func
    exit_code: int = handler(args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
