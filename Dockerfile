# XAU-AI production image (Linux). MetaTrader5 is Windows-only and intentionally
# NOT installed here — the container uses the TwelveData cloud provider.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install the package (build backend + deps declared in pyproject.toml).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

# Runtime assets.
COPY config ./config
COPY scripts/entrypoint.sh ./scripts/entrypoint.sh

# Non-root user; writable dirs for journal/logs.
RUN chmod +x scripts/entrypoint.sh \
    && useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/journal /app/logs \
    && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["scripts/entrypoint.sh"]
