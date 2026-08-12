#!/usr/bin/env bash
# Runs the backend and frontend test suites together in one command,
# failing (non-zero exit) on any failure. Build Prompt 16, deliverable 5.
#
# Assumes: apps/api/.venv is set up (see README) and a Postgres instance
# is reachable at the DATABASE_URL apps/api/tests/conftest.py hardcodes
# (local docker-compose or the CI postgres service both satisfy this).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

echo "==> Backend tests (pytest)"
(cd apps/api && ./.venv/bin/python -m pytest -q)

echo "==> Frontend unit tests (vitest)"
pnpm --filter web test

echo "==> Frontend typecheck"
pnpm --filter web exec tsc --noEmit

echo "All suites passed."
