# XAU-AI

Modular AI analysis system for **XAUUSD (Gold)** intraday trading on **M1 / M5**.

Each analytical concern is an independent **Skill** (Market Structure, Liquidity,
Order Blocks, FVG, ...). A **Validator** aggregates their results with a weighted
model and hard conditions, and a **Signal Generator** emits exactly one of:

- `LONG`
- `SHORT`
- `NO_TRADE`

No intermediate recommendations.

## Status

Stage 0 — foundation: core models, skill registry, config loader, data-provider
abstraction, tests. Analytical skills land in later stages (see roadmap).

## Design principles

- Strict typing (MyPy strict), Ruff + Black clean.
- Open/Closed: new Skills / data sources / notifiers plug in without touching the core.
- Secrets only in `.env` (git-ignored) — never in code or config.
- Honest scoring: `score` is a calibrated confidence, not a literal probability.

## Layout

```
src/xau_ai/
  core/      models, registry, orchestrator, exceptions
  config/    settings loader (YAML + .env)
  data/      DataProvider abstraction (csv, mt5, cloud APIs)
  skills/    independent analytical modules
```

## Dev quickstart

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
ruff check .
mypy
pytest
```

> Note: on the Linux production server (`MetaTrader5` is Windows-only) the data
> layer uses a cloud provider (OANDA / TwelveData). MT5 is for local dev/backtest.
