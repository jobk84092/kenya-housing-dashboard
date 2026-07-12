#!/usr/bin/env bash
# Fast deploy: git pull + rebuild container (no agent-office impact).
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/kenya-housing-dashboard}"
HOST="${CONTABO_HOST:-contabo}"

if [[ "${1:-}" != "--local" ]]; then
  ssh -o BatchMode=yes "$HOST" "APP_DIR=$APP_DIR bash $APP_DIR/deploy/deploy.sh --local"
  exit 0
fi

cd "$APP_DIR"
git pull --ff-only origin main
cd deploy
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8502/_stcore/health && echo " OK"
