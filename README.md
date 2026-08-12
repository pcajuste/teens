# Teenure — dev bootstrap

Product spec of record: `Teenure_MVP_Gameplan.md`. Build sequence: `Teenure_Build_Prompts.md`.

## Layout

- `apps/web` — Next.js 14 App Router (marketing + rep/brand/recruiter/admin portals)
- `apps/api` — FastAPI backend
- `packages/shared-types` — shared TypeScript types

## Setup

```bash
cp .env.example .env.local   # fill in real values, never commit this file
pnpm install
```

## Run in dev

Ports 3000 and 8000 may already be in use by other local projects (e.g.
Docker-hosted apps) — this repo defaults to 3100/8001 instead. Adjust if
those are free/taken differently on your machine.

**Web:**

```bash
cd apps/web && pnpm next dev -p 3100
```

**API** (from `apps/api`, using a virtualenv):

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8001
```

`GET http://127.0.0.1:8001/health` should return `{"status": "ok"}`.

`app/core/config.py` fails fast at startup if any required env var
(see `.env.example`) is missing — copy `.env.example` to `.env.local`
in `apps/api/` before running.

**Tests:** `cd apps/api && source .venv/bin/activate && pytest -q`
(fixtures in `app/tests/conftest.py` stub Settings and mint fake JWTs
per role — no real Supabase/Stripe/Resend credentials needed).

## Database

Schema lives in `supabase/migrations/` (applied verbatim/extended from
Section 7 of the gameplan). Against a real Supabase project, apply these
with the Supabase CLI/dashboard — `auth.users` and `auth.uid()` already
exist there.

To exercise the schema and RLS policies against a **plain local Postgres**
(no Supabase project needed), this repo also ships a minimal stand-in for
Supabase's auth schema under `scripts/local-dev/`:

```bash
cd scripts/local-dev && docker compose up -d   # Postgres on localhost:5434

export PGPASSWORD=teenure_dev_only
for f in scripts/local-dev/000_supabase_stub.sql \
         supabase/migrations/0001_extensions_and_enums.sql \
         supabase/migrations/0002_tables.sql \
         supabase/migrations/0003_indexes.sql \
         supabase/migrations/0004_row_level_security.sql \
         supabase/migrations/0005_consent_token_tracking.sql \
         supabase/migrations/0006_invite_expiry.sql \
         scripts/seed_dev.sql; do
  psql -h 127.0.0.1 -p 5434 -U teenure -d teenure -v ON_ERROR_STOP=1 -f "$f"
done
```

`0005_consent_token_tracking.sql` adds `consent_token_created_at` /
`consent_token_expires_at` / `consent_token_used_at` to `public.users` —
an addition beyond Section 7's literal schema, needed by Prompt 4's
72-hour parental-consent expiry and "already used" error state.

`0006_invite_expiry.sql` adds `invite_expires_at` to `public.campaign_reps`
— needed by Prompt 5's 48-hour campaign-invite deadline and the
`expire_invites` scheduled job (`app/jobs/runner.py`, run via
`POST /internal/jobs/run/expire_invites` on a Railway cron interval).

`scripts/seed_dev.sql` is dev-only fixture data (one user per role) —
never run it against production. See `docs/rep-cached-fields-sync.md` for
how the `rep_profiles` cached fields stay in sync.
