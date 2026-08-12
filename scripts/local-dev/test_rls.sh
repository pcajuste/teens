#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
docker exec -i teenure_postgres psql -U teenure -d teenure < "$REPO_ROOT/scripts/local-dev/test_rls.sql"
