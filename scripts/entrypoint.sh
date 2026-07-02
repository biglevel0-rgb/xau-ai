#!/bin/sh
# XAU-AI service loop: analyse on an interval and push LONG/SHORT to Telegram.
# All settings come from environment variables (see docker-compose.yml / .env).
set -eu

INTERVAL="${ANALYZE_INTERVAL_SECONDS:-300}"
PROVIDER="${DATA_PROVIDER:-twelvedata}"
SYMBOL="${SYMBOL:-XAUUSD}"
SIGNAL_TF="${SIGNAL_TF:-M5}"
CONFIG="${CONFIG_PATH:-config/settings.yaml}"

echo "XAU-AI service starting: provider=${PROVIDER} symbol=${SYMBOL} tf=${SIGNAL_TF} interval=${INTERVAL}s"

while true; do
    xau analyze \
        --provider "${PROVIDER}" \
        --symbol "${SYMBOL}" \
        --tf "${SIGNAL_TF}" \
        --config "${CONFIG}" \
        --notify || echo "analyze cycle failed (continuing)"
    sleep "${INTERVAL}"
done
