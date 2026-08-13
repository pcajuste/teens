#!/usr/bin/env bash
# Pre-flight for `docker compose up`: makes sure the local Supabase CLI
# stack (Postgres/Auth, used by apps/api and apps/web) is running before
# starting the web/api containers, so `./scripts/dc-up.sh` is the only
# command needed for a full local dev environment.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v supabase >/dev/null 2>&1; then
  echo "==> Error: supabase CLI not found. Install it: brew install supabase/tap/supabase" >&2
  exit 1
fi

echo "==> Ensuring local Supabase stack is running..."
supabase start

echo "==> Starting web + api containers..."
docker compose up -d "$@"
