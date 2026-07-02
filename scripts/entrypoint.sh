#!/bin/sh
# XAU-AI service loop.
# MODE=signal   -> vetted trade signals (gates applied), LONG/SHORT only
# MODE=forecast -> directional bias estimate every cycle (no gates)
# All settings come from environment variables (see docker-compose.yml / .env).
set -eu

MODE="${MODE:-signal}"
INTERVAL="${ANALYZE_INTERVAL_SECONDS:-300}"
PROVIDER="${DATA_PROVIDER:-twelvedata}"
SYMBOL="${SYMBOL:-XAUUSD}"
SIGNAL_TF="${SIGNAL_TF:-M5}"
CONFIG="${CONFIG_PATH:-config/settings.yaml}"

echo "XAU-AI service starting: mode=${MODE} provider=${PROVIDER} symbol=${SYMBOL} interval=${INTERVAL}s"

while true; do
    if [ "${MODE}" = "forecast" ]; then
        xau forecast \
            --provider "${PROVIDER}" \
            --symbol "${SYMBOL}" \
            --config "${CONFIG}" \
            --notify || echo "forecast cycle failed (continuing)"
    else
        xau analyze \
            --provider "${PROVIDER}" \
            --symbol "${SYMBOL}" \
            --tf "${SIGNAL_TF}" \
            --config "${CONFIG}" \
            --notify || echo "analyze cycle failed (continuing)"
    fi
    sleep "${INTERVAL}"
done
