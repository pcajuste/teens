#!/usr/bin/env bash
# Applies every file in supabase/migrations/ in filename order to the
# local dev Postgres container (see docker-compose.yml in this dir).
# Local-dev only -- never point this at a real Supabase project;
# use the Supabase CLI / dashboard migration flow there instead.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MIGRATIONS_DIR="$REPO_ROOT/supabase/migrations"
CONTAINER=teenure_postgres
DB_USER=teenure
DB_NAME=teenure

for f in "$MIGRATIONS_DIR"/*.sql; do
  echo "Applying $(basename "$f") ..."
  docker exec -i "$CONTAINER" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" < "$f"
done

echo "All migrations applied."
