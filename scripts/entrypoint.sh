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

# On the very first start, initialise period markers so we don't immediately
# blast weekly/monthly reports built on an empty journal.
init_report_markers() {
    mkdir -p journal
    [ -f journal/.last_weekly ] || date -u +%G-W%V > journal/.last_weekly
    [ -f journal/.last_monthly ] || date -u +%Y-%m > journal/.last_monthly
}

maybe_reports() {
    hour=$(date -u +%H)
    [ "$hour" -lt "$REPORT_HOUR" ] && return 0

    today=$(date -u +%F)
    if [ "$(cat journal/.last_report 2>/dev/null)" != "$today" ]; then
        xau report --period daily --config "${CONFIG}" --notify \
            && echo "$today" > journal/.last_report \
            || echo "daily report failed (continuing)"
    fi

    week=$(date -u +%G-W%V)
    if [ "$(cat journal/.last_weekly 2>/dev/null)" != "$week" ]; then
        xau report --period weekly --config "${CONFIG}" --notify \
            && echo "$week" > journal/.last_weekly \
            || echo "weekly report failed (continuing)"
    fi

    month=$(date -u +%Y-%m)
    if [ "$(cat journal/.last_monthly 2>/dev/null)" != "$month" ]; then
        xau report --period monthly --config "${CONFIG}" --notify \
            && echo "$month" > journal/.last_monthly \
            || echo "monthly report failed (continuing)"
    fi
}

init_report_markers

while true; do
    if [ "$SCHEDULE" = "auto" ] && market_closed; then
        # Tell the owner once per weekend that silence is intentional.
        wk=$(date -u +%G-W%V)
        if [ "$(cat journal/.weekend_notice 2>/dev/null)" != "$wk" ]; then
            xau notify --config "${CONFIG}" \
                --text "💤 Рынок золота закрыт (выходные). Прогнозы возобновятся в воскресенье ~22:00 UTC." \
                && echo "$wk" > journal/.weekend_notice \
                || echo "weekend notice failed (continuing)"
        fi
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

    maybe_reports
    sleep "$(pick_sleep)"
done
