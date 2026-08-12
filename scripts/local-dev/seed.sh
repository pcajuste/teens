#!/usr/bin/env bash
# Dev-only. Loads scripts/local-dev/seed.sql into the local Postgres
# container. Safe to run repeatedly (idempotent).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
docker exec -i teenure_postgres psql -v ON_ERROR_STOP=1 -U teenure -d teenure < "$REPO_ROOT/scripts/local-dev/seed.sql"
