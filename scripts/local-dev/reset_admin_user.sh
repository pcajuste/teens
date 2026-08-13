#!/usr/bin/env bash
# Dev-only. Creates (or resets) a local admin account against the
# Supabase CLI stack (GoTrue + Postgres on port 54321/54322) that
# apps/web's real login flow talks to -- NOT the bare pytest Postgres
# that scripts/local-dev/seed.sh targets, and admin has no self-serve
# signup route (Build Prompt 13 auth note), so this is the only way to
# get an admin account locally.
#
# Safe to re-run: deletes any existing auth user with this email first,
# so it always leaves you with a fresh, known-good admin login.
#
# Usage: scripts/local-dev/reset_admin_user.sh
#   ADMIN_EMAIL=other@teenure.dev ADMIN_PASSWORD=... scripts/local-dev/reset_admin_user.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/apps/api/.env.local"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE -- copy .env.example and fill it in first (see README.md)." >&2
  exit 1
fi

SUPABASE_URL="http://localhost:54321"
SERVICE_KEY="$(grep -E '^SUPABASE_SERVICE_ROLE_KEY=' "$ENV_FILE" | cut -d= -f2-)"
if [ -z "$SERVICE_KEY" ]; then
  echo "SUPABASE_SERVICE_ROLE_KEY not set in $ENV_FILE." >&2
  exit 1
fi

ADMIN_EMAIL="${ADMIN_EMAIL:-admin@teenure.dev}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-AdminDev123!}"
DB_CONTAINER="supabase_db_teenure"

auth_api() {
  curl -sf -H "apikey: $SERVICE_KEY" -H "Authorization: Bearer $SERVICE_KEY" -H "Content-Type: application/json" "$@"
}

echo "Removing any existing auth user for $ADMIN_EMAIL ..."
EXISTING_ID="$(auth_api "$SUPABASE_URL/auth/v1/admin/users?email=$ADMIN_EMAIL" \
  | python3 -c 'import json,sys; users=json.load(sys.stdin).get("users",[]); print(users[0]["id"] if users else "")')"
if [ -n "$EXISTING_ID" ]; then
  auth_api -X DELETE "$SUPABASE_URL/auth/v1/admin/users/$EXISTING_ID" >/dev/null
  echo "Deleted existing auth user $EXISTING_ID."
fi

echo "Creating auth user $ADMIN_EMAIL ..."
CREATE_RESPONSE="$(auth_api -X POST "$SUPABASE_URL/auth/v1/admin/users" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\",\"email_confirm\":true}")"
USER_ID="$(echo "$CREATE_RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"

echo "Setting app_metadata (role=admin, account_status=active) -- apps/api/app/core/security.py reads role/account_status from this JWT claim, not public.users ..."
auth_api -X PUT "$SUPABASE_URL/auth/v1/admin/users/$USER_ID" \
  -d '{"app_metadata":{"role":"admin","account_status":"active"}}' >/dev/null

echo "Upserting public.users row ..."
docker exec -i "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d postgres <<SQL
INSERT INTO public.users (id, email, role, account_status, date_of_birth)
VALUES ('$USER_ID', '$ADMIN_EMAIL', 'admin', 'active', (CURRENT_DATE - INTERVAL '30 years')::date)
ON CONFLICT (id) DO UPDATE SET role = 'admin', account_status = 'active';
SQL

cat <<MSG

Admin account ready:
  URL:      /admin-login
  Email:    $ADMIN_EMAIL
  Password: $ADMIN_PASSWORD

If you were already signed in as this user, sign out and back in --
your old session's JWT was minted before this reset and won't carry
the new claims.
MSG
