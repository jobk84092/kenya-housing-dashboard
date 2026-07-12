#!/usr/bin/env bash
# Install or update Kenya Housing Dashboard on Contabo.
# From Mac: bash deploy/install_contabo.sh
# On server: bash /opt/kenya-housing-dashboard/deploy/install_contabo.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/kenya-housing-dashboard}"
REPO="${REPO:-https://github.com/jobk84092/kenya-housing-dashboard.git}"
HOST="${CONTABO_HOST:-}"

if [[ -n "$HOST" && "${1:-}" != "--local" ]]; then
  ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" "APP_DIR=$APP_DIR bash -s -- --local" < "$0"
  exit 0
fi

echo "=== Kenya Housing Dashboard — Contabo install ==="

if [[ ! -d "$APP_DIR/.git" ]]; then
  sudo mkdir -p "$(dirname "$APP_DIR")"
  sudo git clone "$REPO" "$APP_DIR"
  sudo chown -R deploy:deploy "$APP_DIR"
fi

cd "$APP_DIR"
git pull --ff-only origin main

chmod +x deploy/*.sh

if [[ ! -f .streamlit/secrets.toml ]]; then
  echo "WARN: .streamlit/secrets.toml missing — copy from secrets.example.toml and add API keys"
  cp .streamlit/secrets.example.toml .streamlit/secrets.toml
  chmod 600 .streamlit/secrets.toml
fi

echo "=== Build & start container ==="
cd deploy
docker compose up -d --build

echo "=== Install systemd unit (optional, requires sudo) ==="
if command -v systemctl >/dev/null 2>&1; then
  sudo cp "$APP_DIR/deploy/kenya-housing-dashboard.service" /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable kenya-housing-dashboard.service || true
fi

echo "=== Health check cron (every 15 min) ==="
CRON_LINE="*/15 * * * * bash $APP_DIR/deploy/health_check.sh"
MARKER="kenya-housing-health"
if crontab -l 2>/dev/null | grep -q "$MARKER"; then
  (crontab -l 2>/dev/null | grep -v "$MARKER"; echo "$CRON_LINE # $MARKER") | crontab -
else
  (crontab -l 2>/dev/null; echo "$CRON_LINE # $MARKER") | crontab -
fi

echo "=== Done ==="
docker compose ps
curl -fsS http://127.0.0.1:8502/_stcore/health && echo " Health OK" || echo " Health check pending (wait ~30s)"
