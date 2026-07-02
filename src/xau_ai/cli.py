"""Command-line entry point for XAU-AI.

Usage::

    xau show-data --dir ./data_cache --symbol XAUUSD --tf M1,M5 --count 5
    xau analyze   --dir ./data_cache --symbol XAUUSD --tf M5 --config config/settings.yaml
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

from xau_ai.config.settings import load_settings
from xau_ai.core.context import build_context
from xau_ai.core.exceptions import DataProviderError, XauAiError
from xau_ai.core.models import Candle, MarketContext, Signal, SignalType, Timeframe
from xau_ai.data.base import DataProvider
from xau_ai.data.csv_provider import CsvDataProvider


def _make_provider(name: str, data_dir: str) -> DataProvider:
    """Build the selected data provider (CSV for local, TwelveData for cloud)."""
    if name == "csv":
        return CsvDataProvider(Path(data_dir))
    if name == "twelvedata":
        from xau_ai.config.settings import Secrets
        from xau_ai.data.twelvedata import TwelveDataProvider

        return TwelveDataProvider(Secrets().twelvedata_api_key)
    if name == "oanda":
        from xau_ai.config.settings import Secrets
        from xau_ai.data.oanda import OandaDataProvider

        secrets = Secrets()
        return OandaDataProvider(secrets.oanda_api_token, secrets.oanda_env)
    raise DataProviderError(f"unknown provider: {name}")


def _add_provider_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", default="csv", choices=["csv", "twelvedata", "oanda"])


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
        signal_tf = _parse_timeframes(args.tf)[0]
        provider = _make_provider(args.provider, args.dir)
        # Load every configured timeframe (for MTF) + correlated instruments.
        related = {symbol: signal_tf for symbol in settings.related_symbols}
        ctx = build_context(provider, args.symbol, settings.timeframes, args.count, related=related)
        signal = Orchestrator(settings, signal_tf).analyze(ctx)
    except XauAiError as exc:
        print(f"error: {exc}")
        return 1
    _print_signal(signal)
    if args.notify:
        _maybe_notify(settings, signal)
    return 0


def _maybe_notify(settings: object, signal: Signal) -> None:
    from xau_ai.config.settings import Secrets, Settings
    from xau_ai.core.exceptions import NotificationError
    from xau_ai.notifications.telegram import TelegramNotifier

    assert isinstance(settings, Settings)
    telegram = settings.notifications.telegram
    if not telegram.enabled:
        print("  (telegram disabled)")
        return
    secrets = Secrets()
    notifier = TelegramNotifier(
        secrets.telegram_bot_token,
        secrets.telegram_owner_chat_id,
        telegram.send_on,
    )
    try:
        sent = notifier.notify(signal)
    except NotificationError as exc:
        print(f"  notify error: {exc}")
        return
    print("  telegram: sent" if sent else "  telegram: skipped (not an actionable signal)")


def _cmd_backtest(args: argparse.Namespace) -> int:
    from xau_ai.backtesting.backtester import Backtester
    from xau_ai.core.orchestrator import Orchestrator
    from xau_ai.performance.metrics import compute_performance

    try:
        settings = load_settings(args.config)
        timeframe = _parse_timeframes(args.tf)[0]
        provider = _make_provider(args.provider, args.dir)
        candles = provider.get_candles(args.symbol, timeframe, args.count)
    except XauAiError as exc:
        print(f"error: {exc}")
        return 1

    source = Orchestrator(settings, timeframe)
    backtester = Backtester(source, args.symbol, timeframe, warmup=args.warmup)
    report = compute_performance(backtester.run(candles))
    _print_report(report, bars=len(candles))
    return 0


def _print_report(report: object, bars: int) -> None:
    from xau_ai.performance.metrics import PerformanceReport

    assert isinstance(report, PerformanceReport)
    print("-" * 44)
    print(f"  BACKTEST REPORT  ({bars} bars)")
    print("-" * 44)
    print(f"  Trades:          {report.trades}")
    print(f"  Win rate:        {report.win_rate:.1%}")
    print(f"  Total:           {report.total_r:+.2f} R")
    print(f"  Expectancy:      {report.expectancy_r:+.2f} R")
    print(f"  Profit factor:   {report.profit_factor:.2f}")
    print(f"  Max drawdown:    {report.max_drawdown_r:.2f} R")
    print(f"  Sharpe:          {report.sharpe:.2f}")
    print(f"  Sortino:         {report.sortino:.2f}")
    print(f"  Recovery factor: {report.recovery_factor:.2f}")
    print("-" * 44)


def _cmd_calibrate(args: argparse.Namespace) -> int:
    from xau_ai.calibration.calibrator import Calibrator

    try:
        settings = load_settings(args.config)
        timeframe = _parse_timeframes(args.tf)[0]
        provider = _make_provider(args.provider, args.dir)
        candles = provider.get_candles(args.symbol, timeframe, args.count)
        calibrator = Calibrator(settings, timeframe, warmup=args.warmup, symbol=args.symbol)
        result = calibrator.calibrate(candles, metric=args.metric)
    except XauAiError as exc:
        print(f"error: {exc}")
        return 1

    print("-" * 44)
    print(f"  CALIBRATION  (metric: {args.metric})")
    print("-" * 44)
    print(f"  Best score:  {result.best_score:+.3f}")
    print("  Best weights:")
    for name, weight in sorted(result.best_weights.items()):
        print(f"    {name:>18}: {weight:.3f}")
    print(f"  Trades:      {result.best_report.trades}")
    print(f"  Win rate:    {result.best_report.win_rate:.1%}")
    print(f"  Expectancy:  {result.best_report.expectancy_r:+.2f} R")
    print("-" * 44)
    return 0


def _cmd_forecast(args: argparse.Namespace) -> int:
    """Directional bias forecast: always reports which side currently outweighs.

    Unlike ``analyze`` this does NOT apply the confidence/RR gates — it exposes
    the validator's raw vote. It is a market-direction estimate, not a vetted
    trade signal.
    """
    from xau_ai.core.orchestrator import Orchestrator
    from xau_ai.core.registry import registry
    from xau_ai.data.resample import resample
    from xau_ai.forecasting.tracker import ForecastTracker
    from xau_ai.skills.correlation.skill import (
        DEFAULT_RELATIONSHIPS,
        CorrelationSkill,
        Relationship,
    )
    from xau_ai.validator.validator import Validator

    try:
        settings = load_settings(args.config)
        provider = _make_provider(args.provider, args.dir)
        # One M1 fetch serves M1/M5/M15 via local resampling (API-limit friendly).
        m1 = provider.get_candles(args.symbol, Timeframe.M1, args.count)

        # Correlated instruments (best-effort: a missing one is skipped).
        related: dict[str, list[Candle]] = {}
        for rel_symbol in settings.related_symbols:
            with contextlib.suppress(DataProviderError):
                related[rel_symbol] = provider.get_candles(rel_symbol, Timeframe.M5, 300)

        ctx = MarketContext(
            symbol=args.symbol,
            as_of=m1[-1].timestamp,
            series={
                Timeframe.M1: m1,
                Timeframe.M5: resample(m1, Timeframe.M5),
                Timeframe.M15: resample(m1, Timeframe.M15),
            },
            related=related,
        )

        # Custom-configured skills replace their default registrations.
        from xau_ai.skills.base import BaseSkill

        excluded = {"correlation"}
        skills: list[BaseSkill] = []
        if related:
            reference = next(iter(related))
            relationship = DEFAULT_RELATIONSHIPS.get(reference, Relationship.INVERSE)
            skills.append(CorrelationSkill(reference=reference, relationship=relationship))
        if args.news:
            from xau_ai.data.news.faireconomy import FaireconomyNewsProvider
            from xau_ai.skills.news import NewsFilterSkill

            excluded.add("news")
            cache = Path(args.journal).parent / "news_cache.json"
            skills.append(
                NewsFilterSkill(
                    FaireconomyNewsProvider(cache_path=cache),
                    block_minutes_before=settings.news.block_minutes_before,
                    block_minutes_after=settings.news.block_minutes_after,
                )
            )
        skills.extend(cls() for cls in registry.all() if cls.name not in excluded)

        orch = Orchestrator(settings, Timeframe.M5, skills=skills)
        results = orch.run_skills(ctx)
        agg = Validator(settings.validator).aggregate(results)

        # Self-verification: grade past forecasts against what actually happened,
        # then record this one for future grading.
        tracker = ForecastTracker(args.journal, horizon_min=args.horizon)
        tracker.evaluate_pending(m1)
    except XauAiError as exc:
        print(f"error: {exc}")
        return 1

    price = m1[-1].close
    if agg.direction.value == "LONG":
        icon, label = "⬆", "LONG"
    elif agg.direction.value == "SHORT":
        icon, label = "⬇", "SHORT"
    else:
        icon, label = "→", "FLAT"

    tracker.record(ctx.as_of, label, agg.confidence, price)

    # High-confidence alert: bias reached the vetted-signal threshold.
    threshold = settings.validator.confidence_threshold
    strong = agg.direction.value != "NEUTRAL" and agg.confidence >= threshold
    vetoes = [r for r in results if r.veto]

    lines = []
    for veto in vetoes:
        detail = veto.evidence[0] if veto.evidence else veto.skill_name
        lines.append(f"⚠️ {detail} — trading not advised")
    if strong:
        lines.append(f"🚨 STRONG {label} — confidence {agg.confidence:.0%} (>= {threshold:.0%})")
    lines.append(f"🔮 {args.symbol} forecast (M5): {icon} {label} {agg.confidence:.0%}")
    lines.append(f"Price: {price:.2f} @ {ctx.as_of.strftime('%H:%M')} UTC")
    if agg.agreeing:
        lines.append("For: " + ", ".join(agg.agreeing))
    if agg.disagreeing:
        lines.append("Against: " + ", ".join(agg.disagreeing))
    lines.append("(bias estimate, not a vetted trade signal)")
    text = "\n".join(lines)
    print(text)

    if args.notify:
        _send_forecast(settings, text)
    return 0


def _send_forecast(settings: object, text: str) -> None:
    from xau_ai.config.settings import Secrets, Settings
    from xau_ai.core.exceptions import NotificationError
    from xau_ai.notifications.telegram import TelegramNotifier

    assert isinstance(settings, Settings)
    if not settings.notifications.telegram.enabled:
        print("  (telegram disabled)")
        return
    secrets = Secrets()
    notifier = TelegramNotifier(secrets.telegram_bot_token, secrets.telegram_owner_chat_id)
    try:
        notifier.send_text(text)
        print("  telegram: sent")
    except NotificationError as exc:
        print(f"  notify error: {exc}")


def _cmd_report(args: argparse.Namespace) -> int:
    """Daily accuracy summary built from the forecast journal."""
    from datetime import UTC, datetime

    from xau_ai.forecasting.tracker import ForecastTracker

    try:
        settings = load_settings(args.config)
        tracker = ForecastTracker(args.journal)
        now = datetime.now(UTC).replace(tzinfo=None)
        stats = tracker.stats(now, window_hours=args.window)
    except XauAiError as exc:
        print(f"error: {exc}")
        return 1

    lines = [f"📊 XAU-AI daily report (last {args.window}h)"]
    lines.append(f"Forecasts: {stats.total} (pending {stats.pending}, flat {stats.skipped})")
    if stats.correct + stats.wrong > 0:
        lines.append(f"Accuracy: {stats.accuracy:.0%} ({stats.correct}✓ / {stats.wrong}✗)")
        if stats.long_total:
            lines.append(f"LONG: {stats.long_correct}/{stats.long_total} correct")
        if stats.short_total:
            lines.append(f"SHORT: {stats.short_correct}/{stats.short_total} correct")
    else:
        lines.append("Accuracy: no graded forecasts yet")
    lines.append(f"Avg confidence: {stats.avg_confidence:.0%}")
    lines.append(f"Strong alerts (>=85%): {stats.strong_count}")
    text = "\n".join(lines)
    print(text)

    if args.notify:
        _send_forecast(settings, text)
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
    analyze.add_argument(
        "--dir", default="data_cache", help="directory with <SYMBOL>_<TF>.csv files"
    )
    analyze.add_argument("--symbol", default="XAUUSD")
    analyze.add_argument("--tf", default="M5", help="signal timeframe (single)")
    analyze.add_argument("--count", type=int, default=300)
    analyze.add_argument("--config", default="config/settings.yaml")
    _add_provider_arg(analyze)
    analyze.add_argument(
        "--notify", action="store_true", help="send LONG/SHORT to Telegram (owner-only)"
    )
    analyze.set_defaults(func=_cmd_analyze)

    backtest = sub.add_parser("backtest", help="simulate the strategy over history")
    backtest.add_argument(
        "--dir", default="data_cache", help="directory with <SYMBOL>_<TF>.csv files"
    )
    backtest.add_argument("--symbol", default="XAUUSD")
    backtest.add_argument("--tf", default="M5", help="signal timeframe (single)")
    backtest.add_argument("--count", type=int, default=5000)
    backtest.add_argument("--warmup", type=int, default=60)
    backtest.add_argument("--config", default="config/settings.yaml")
    _add_provider_arg(backtest)
    backtest.set_defaults(func=_cmd_backtest)

    calibrate = sub.add_parser("calibrate", help="tune validator weights on history")
    calibrate.add_argument(
        "--dir", default="data_cache", help="directory with <SYMBOL>_<TF>.csv files"
    )
    calibrate.add_argument("--symbol", default="XAUUSD")
    calibrate.add_argument("--tf", default="M5", help="signal timeframe (single)")
    calibrate.add_argument("--count", type=int, default=5000)
    calibrate.add_argument("--warmup", type=int, default=60)
    calibrate.add_argument(
        "--metric", default="expectancy", choices=["expectancy", "profit_factor", "total_r"]
    )
    calibrate.add_argument("--config", default="config/settings.yaml")
    _add_provider_arg(calibrate)
    calibrate.set_defaults(func=_cmd_calibrate)

    forecast = sub.add_parser("forecast", help="directional bias estimate (no gates)")
    forecast.add_argument("--dir", default="data_cache", help="CSV dir (csv provider only)")
    forecast.add_argument("--symbol", default="XAUUSD")
    forecast.add_argument("--count", type=int, default=900, help="M1 bars to fetch")
    forecast.add_argument("--config", default="config/settings.yaml")
    forecast.add_argument("--journal", default="journal/forecasts.jsonl")
    forecast.add_argument("--horizon", type=int, default=30, help="grading horizon, minutes")
    forecast.add_argument("--news", action="store_true", help="enable live economic calendar")
    _add_provider_arg(forecast)
    forecast.add_argument("--notify", action="store_true", help="send to Telegram (owner-only)")
    forecast.set_defaults(func=_cmd_forecast)

    report = sub.add_parser("report", help="accuracy summary from the forecast journal")
    report.add_argument("--journal", default="journal/forecasts.jsonl")
    report.add_argument("--window", type=int, default=24, help="hours to summarise")
    report.add_argument("--config", default="config/settings.yaml")
    report.add_argument("--notify", action="store_true", help="send to Telegram (owner-only)")
    report.set_defaults(func=_cmd_report)
    return parser


def _force_utf8_output() -> None:
    """Make stdout/stderr UTF-8 so decorative glyphs never crash a legacy console."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(ValueError, OSError):
                reconfigure(encoding="utf-8", errors="replace")


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
