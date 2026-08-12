#!/usr/bin/env bash
# Start apps/web (Next.js) and apps/api (FastAPI) together for local dev.
# Ctrl-C stops both.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

API_DIR="apps/api"
WEB_DIR="apps/web"
API_PORT="${API_PORT:-8300}"
WEB_PORT="${WEB_PORT:-3300}"

if [ ! -d "$API_DIR/.venv" ]; then
  echo "==> Creating apps/api virtualenv..."
  python3.11 -m venv "$API_DIR/.venv"
  "$API_DIR/.venv/bin/pip" install -q -r "$API_DIR/requirements.txt"
fi

if [ ! -d "node_modules" ]; then
  echo "==> Installing workspace dependencies..."
  pnpm install
fi

if [ ! -f "$API_DIR/.env.local" ]; then
  echo "==> Warning: $API_DIR/.env.local not found. apps/api will fail to start"
  echo "    without required env vars — see .env.example at repo root."
fi

pids=()
cleanup() {
  echo "==> Stopping dev servers..."
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Starting apps/api on :$API_PORT"
(
  cd "$API_DIR"
  source .venv/bin/activate
  uvicorn app.main:app --reload --port "$API_PORT"
) &
pids+=($!)

echo "==> Starting apps/web on :$WEB_PORT"
(
  cd "$WEB_DIR"
  pnpm dev --port "$WEB_PORT"
) &
pids+=($!)

wait
