#!/usr/bin/env bash
# Health check — exit 1 if dashboard is down (for cron / UptimeRobot webhook).
set -euo pipefail

URL="${KENYA_HOUSING_HEALTH_URL:-http://127.0.0.1:8502/_stcore/health}"
LOG="${LOG:-/home/deploy/housing-data/kenya-housing-health.log}"

mkdir -p "$(dirname "$LOG")"

if curl -fsS --max-time 15 "$URL" >/dev/null; then
  echo "$(date -Iseconds) OK $URL" >> "$LOG"
  exit 0
fi

echo "$(date -Iseconds) FAIL $URL — attempting restart" >> "$LOG"
if [[ -d "$HOME/kenya-housing-dashboard/deploy" ]]; then
  (cd "$HOME/kenya-housing-dashboard/deploy" && docker compose restart kenya-housing) >> "$LOG" 2>&1 || true
elif [[ -d /opt/kenya-housing-dashboard/deploy ]]; then
  (cd /opt/kenya-housing-dashboard/deploy && docker compose restart kenya-housing) >> "$LOG" 2>&1 || true
fi
exit 1
