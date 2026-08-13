#!/usr/bin/env bash
# Dev-only. Resets the local Supabase CLI stack (`supabase db reset` --
# drops and reapplies every migration in supabase/migrations/) and then
# creates sample logins covering every role: talent (adult + minor),
# brand, recruiter, admin -- against the same GoTrue + Postgres stack
# apps/web's real login flow talks to (NOT the bare pytest Postgres
# that scripts/local-dev/seed.sh targets).
#
# Two talent accounts on purpose, not one: talent@teenure.dev is 18+
# (no parental-consent gate at all), talent-minor@teenure.dev is 15
# (under the under-16 double opt-in threshold, Section 9). Exercising
# both boundary cases matters here since the age gate is a
# compliance/legal requirement, not a style preference.
#
# Admin creation is delegated to reset_admin_user.sh (same script the
# README already documents standalone) so there's one source of truth
# for how an admin login gets minted.
#
# Parent is NOT a password login -- per app/routers/parent_auth.py,
# parents only ever get in via a magic link tied to a specific minor
# talent's parent_records row (Section 9A: no parent account exists
# independent of a talent). So instead of a fake parent@teenure.dev
# password account, this links parent@teenure.dev to
# talent-minor@teenure.dev via an already-verified parent_records row
# and mints a ready-to-use parent portal session JWT directly (skips
# needing Resend/email delivery for local dev).
#
# Safe to re-run: each user is deleted and recreated, so it always
# leaves you with fresh, known-good logins.
#
# Usage: scripts/local-dev/reset_sample_users.sh
#   SKIP_DB_RESET=1 scripts/local-dev/reset_sample_users.sh   # keep existing data/migrations state
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/apps/api/.env.local"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE -- copy .env.example and fill it in first (see README.md)." >&2
  exit 1
fi

SUPABASE_URL="http://localhost:54321"
SERVICE_KEY="$(grep -E '^SUPABASE_SERVICE_ROLE_KEY=' "$ENV_FILE" | cut -d= -f2-)"
PARENT_SESSION_SECRET="$(grep -E '^PARENT_SESSION_SECRET=' "$ENV_FILE" | cut -d= -f2-)"
if [ -z "$SERVICE_KEY" ]; then
  echo "SUPABASE_SERVICE_ROLE_KEY not set in $ENV_FILE." >&2
  exit 1
fi
if [ -z "$PARENT_SESSION_SECRET" ]; then
  echo "PARENT_SESSION_SECRET not set in $ENV_FILE." >&2
  exit 1
fi

DB_CONTAINER="supabase_db_teenure"
TALENT_ADULT_EMAIL="talent@teenure.dev"
TALENT_MINOR_EMAIL="talent-minor@teenure.dev"
BRAND_EMAIL="brand@teenure.dev"
RECRUITER_EMAIL="recruiter@teenure.dev"
PARENT_EMAIL="parent@teenure.dev"
SAMPLE_PASSWORD="SampleDev123!"

psql_exec() {
  docker exec -i "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d postgres "$@"
}

auth_api() {
  curl -sf -H "apikey: $SERVICE_KEY" -H "Authorization: Bearer $SERVICE_KEY" -H "Content-Type: application/json" "$@"
}

if [ "${SKIP_DB_RESET:-0}" != "1" ]; then
  echo "Resetting local Supabase DB (drops all data, reapplies migrations) ..."
  ( cd "$REPO_ROOT" && supabase db reset )
else
  echo "SKIP_DB_RESET=1 -- leaving existing DB state as-is."
fi

# Returns the new auth.users id on stdout. Deletes any existing user
# with this email first so re-runs are idempotent.
#
# NB: this local GoTrue's admin list-users endpoint does NOT actually
# filter by the ?email= query param -- it silently returns the full
# user list. Filtering client-side by exact email match is load
# bearing: relying on the query param instead deletes whatever
# happens to be first in the unfiltered list (i.e. some *other*
# sample user), not the intended one.
create_auth_user() {
  local email="$1"
  local existing
  existing="$(auth_api "$SUPABASE_URL/auth/v1/admin/users" \
    | python3 -c "import json,sys; users=json.load(sys.stdin).get('users',[]); matches=[u['id'] for u in users if u['email']=='$email']; print(matches[0] if matches else '')")"
  if [ -n "$existing" ]; then
    auth_api -X DELETE "$SUPABASE_URL/auth/v1/admin/users/$existing" >/dev/null
  fi
  local create_response
  create_response="$(auth_api -X POST "$SUPABASE_URL/auth/v1/admin/users" \
    -d "{\"email\":\"$email\",\"password\":\"$SAMPLE_PASSWORD\",\"email_confirm\":true}")"
  echo "$create_response" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'
}

set_app_metadata() {
  local user_id="$1" role="$2"
  auth_api -X PUT "$SUPABASE_URL/auth/v1/admin/users/$user_id" \
    -d "{\"app_metadata\":{\"role\":\"$role\",\"account_status\":\"active\"}}" >/dev/null
}

echo "Creating talent@teenure.dev (18yo, no parental consent required) ..."
TALENT_ADULT_ID="$(create_auth_user "$TALENT_ADULT_EMAIL")"
set_app_metadata "$TALENT_ADULT_ID" "talent"
psql_exec <<SQL
INSERT INTO public.users (id, email, role, account_status, date_of_birth)
VALUES ('$TALENT_ADULT_ID', '$TALENT_ADULT_EMAIL', 'talent', 'active', (CURRENT_DATE - INTERVAL '18 years')::date)
ON CONFLICT (id) DO UPDATE SET role = 'talent', account_status = 'active';

INSERT INTO public.talent_profiles (user_id, display_name, school_name, city, state, graduation_year, categories, recruiter_visible)
VALUES ('$TALENT_ADULT_ID', 'Sample Talent (Adult)', 'Sample High School', 'Austin', 'TX', 2027, ARRAY['athletics'], TRUE)
ON CONFLICT (user_id) DO UPDATE SET display_name = 'Sample Talent (Adult)';
SQL

echo "Creating talent-minor@teenure.dev (15yo, parent_email=$PARENT_EMAIL, under-16 consent gate) ..."
TALENT_MINOR_ID="$(create_auth_user "$TALENT_MINOR_EMAIL")"
set_app_metadata "$TALENT_MINOR_ID" "talent"
psql_exec <<SQL
INSERT INTO public.users (id, email, role, account_status, date_of_birth, parent_email, parent_verified_at)
VALUES ('$TALENT_MINOR_ID', '$TALENT_MINOR_EMAIL', 'talent', 'active', (CURRENT_DATE - INTERVAL '15 years')::date, '$PARENT_EMAIL', now())
ON CONFLICT (id) DO UPDATE SET role = 'talent', account_status = 'active', parent_email = '$PARENT_EMAIL', parent_verified_at = now();

INSERT INTO public.talent_profiles (user_id, display_name, school_name, city, state, graduation_year, categories, recruiter_visible)
VALUES ('$TALENT_MINOR_ID', 'Sample Talent (Minor)', 'Sample High School', 'Austin', 'TX', 2029, ARRAY['gaming'], TRUE)
ON CONFLICT (user_id) DO UPDATE SET display_name = 'Sample Talent (Minor)';
SQL

echo "Creating brand@teenure.dev ..."
BRAND_ID="$(create_auth_user "$BRAND_EMAIL")"
set_app_metadata "$BRAND_ID" "brand"
psql_exec <<SQL
INSERT INTO public.users (id, email, role, account_status, date_of_birth)
VALUES ('$BRAND_ID', '$BRAND_EMAIL', 'brand', 'active', (CURRENT_DATE - INTERVAL '30 years')::date)
ON CONFLICT (id) DO UPDATE SET role = 'brand', account_status = 'active';

INSERT INTO public.brand_profiles (user_id, company_name, industry, verified)
VALUES ('$BRAND_ID', 'Sample Brand Co.', 'apparel', TRUE)
ON CONFLICT (user_id) DO UPDATE SET company_name = 'Sample Brand Co.';
SQL

echo "Creating recruiter@teenure.dev ..."
RECRUITER_ID="$(create_auth_user "$RECRUITER_EMAIL")"
set_app_metadata "$RECRUITER_ID" "recruiter"
psql_exec <<SQL
INSERT INTO public.users (id, email, role, account_status, date_of_birth)
VALUES ('$RECRUITER_ID', '$RECRUITER_EMAIL', 'recruiter', 'active', (CURRENT_DATE - INTERVAL '35 years')::date)
ON CONFLICT (id) DO UPDATE SET role = 'recruiter', account_status = 'active';

INSERT INTO public.recruiter_profiles (user_id, institution_name, institution_type, verified, contact_credits_remaining)
VALUES ('$RECRUITER_ID', 'Sample State University', 'college', TRUE, 25)
ON CONFLICT (user_id) DO UPDATE SET institution_name = 'Sample State University';
SQL

echo "Seeding parent_records for parent@teenure.dev (linked to talent-minor) and minting a portal session ..."
PARENT_ID="$(psql_exec -q -t -A <<SQL | grep -v '^$'
INSERT INTO public.parent_records (talent_id, parent_email, campaign_approval_required, digest_enabled, portal_expires_at)
SELECT id, '$PARENT_EMAIL', TRUE, TRUE, now() + INTERVAL '3 years'
FROM public.talent_profiles WHERE user_id = '$TALENT_MINOR_ID'
ON CONFLICT (talent_id) DO UPDATE SET parent_email = '$PARENT_EMAIL', portal_expires_at = now() + INTERVAL '3 years'
RETURNING parent_id;
SQL
)"

TALENT_MINOR_PROFILE_ID="$(psql_exec -q -t -A <<SQL | grep -v '^$'
SELECT id FROM public.talent_profiles WHERE user_id = '$TALENT_MINOR_ID';
SQL
)"

PARENT_SESSION_TOKEN="$(PARENT_SESSION_SECRET="$PARENT_SESSION_SECRET" PARENT_ID="$PARENT_ID" TALENT_ID="$TALENT_MINOR_PROFILE_ID" python3 <<'PY'
import os, jwt, time
secret = os.environ["PARENT_SESSION_SECRET"]
now = int(time.time())
payload = {
    "parent_id": os.environ["PARENT_ID"],
    "talent_id": os.environ["TALENT_ID"],
    "iss": "teenure-parent-portal",
    "iat": now,
    "exp": now + 24 * 3600,
}
print(jwt.encode(payload, secret, algorithm="HS256"))
PY
)"

echo "Creating/refreshing admin@teenure.dev via reset_admin_user.sh ..."
"$REPO_ROOT/scripts/local-dev/reset_admin_user.sh"

cat <<MSG

Sample accounts ready (password logins, /login or /admin-login):
  Talent (adult, 18):  $TALENT_ADULT_EMAIL / $SAMPLE_PASSWORD
  Talent (minor, 15):  $TALENT_MINOR_EMAIL / $SAMPLE_PASSWORD  (parent consent already verified)
  Brand:                $BRAND_EMAIL / $SAMPLE_PASSWORD
  Recruiter:             $RECRUITER_EMAIL / $SAMPLE_PASSWORD
  Admin:                 admin@teenure.dev / AdminDev123! (see reset_admin_user.sh output above)

Parent portal (no password -- magic-link only, linked to talent-minor
above via parent_records):
  Normal flow: POST /parent/auth/request-link with
    {"parent_email":"$PARENT_EMAIL"} to email a real sign-in link.
  Instant local session (skips email): use this bearer token directly
  against /parent/* routes, valid 24h:
    $PARENT_SESSION_TOKEN
MSG
