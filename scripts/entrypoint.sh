#!/bin/sh
# XAU-AI service loop.
# MODE=signal   -> vetted trade signals (gates applied), LONG/SHORT only
# MODE=forecast -> directional bias estimate every cycle (no gates)
#
# Session-aware schedule (SCHEDULE=auto, default):
#   weekend (gold market closed)   -> sleep 30 min, skip analysis
#   London/NY hours (07-21 UTC)    -> every ACTIVE_INTERVAL (240s)
#   Asia / off hours               -> every QUIET_INTERVAL (900s)
# Set ANALYZE_INTERVAL_SECONDS to force a fixed interval instead.
# A daily accuracy report is sent once per day after REPORT_HOUR UTC.
set -eu

MODE="${MODE:-signal}"
SCHEDULE="${SCHEDULE:-auto}"
FIXED_INTERVAL="${ANALYZE_INTERVAL_SECONDS:-}"
ACTIVE_INTERVAL="${ACTIVE_INTERVAL_SECONDS:-240}"
QUIET_INTERVAL="${QUIET_INTERVAL_SECONDS:-900}"
REPORT_HOUR="${REPORT_HOUR:-6}"
PROVIDER="${DATA_PROVIDER:-twelvedata}"
SYMBOL="${SYMBOL:-XAUUSD}"
SIGNAL_TF="${SIGNAL_TF:-M5}"
CONFIG="${CONFIG_PATH:-config/settings.yaml}"

echo "XAU-AI service starting: mode=${MODE} schedule=${SCHEDULE} provider=${PROVIDER} symbol=${SYMBOL}"

market_closed() {
    dow=$(date -u +%u)   # 1=Mon .. 7=Sun
    hour=$(date -u +%H)
    [ "$dow" -eq 6 ] && return 0                          # Saturday
    [ "$dow" -eq 7 ] && [ "$hour" -lt 22 ] && return 0    # Sunday before 22:00
    [ "$dow" -eq 5 ] && [ "$hour" -ge 22 ] && return 0    # Friday after 22:00
    return 1
}

pick_sleep() {
    if [ -n "$FIXED_INTERVAL" ]; then echo "$FIXED_INTERVAL"; return; fi
    hour=$(date -u +%H)
    if [ "$hour" -ge 7 ] && [ "$hour" -lt 21 ]; then
        echo "$ACTIVE_INTERVAL"
    else
        echo "$QUIET_INTERVAL"
    fi
}

maybe_daily_report() {
    hour=$(date -u +%H)
    today=$(date -u +%F)
    last=$(cat journal/.last_report 2>/dev/null || echo "")
    if [ "$hour" -ge "$REPORT_HOUR" ] && [ "$last" != "$today" ]; then
        xau report --config "${CONFIG}" --notify \
            && echo "$today" > journal/.last_report \
            || echo "daily report failed (continuing)"
    fi
}

while true; do
    if [ "$SCHEDULE" = "auto" ] && market_closed; then
        echo "market closed (weekend); sleeping 30m"
        sleep 1800
        continue
    fi

    if [ "${MODE}" = "forecast" ]; then
        xau forecast \
            --provider "${PROVIDER}" \
            --symbol "${SYMBOL}" \
            --config "${CONFIG}" \
            --news \
            --notify || echo "forecast cycle failed (continuing)"
    else
        xau analyze \
            --provider "${PROVIDER}" \
            --symbol "${SYMBOL}" \
            --tf "${SIGNAL_TF}" \
            --config "${CONFIG}" \
            --notify || echo "analyze cycle failed (continuing)"
    fi

    maybe_daily_report
    sleep "$(pick_sleep)"
done
