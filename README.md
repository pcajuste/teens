# Teenure — Dev Bootstrap

Monorepo for Teenure. See `Teenure_MVP_Gameplan.md` for the product/technical
spec (source of truth) and `Teenure_Build_Prompts.md` for the build sequence.

## Layout

```
apps/web/            Next.js 14 App Router — marketing + all portals
apps/api/             FastAPI backend
packages/shared-types/ Shared TypeScript types
demo/                  Seed data for public-facing demo experiences
```

## Prerequisites

- Node.js 20+ and [pnpm](https://pnpm.io/)
- Python 3.11+

## Install

```bash
pnpm install
```

## Run both apps at once (recommended)

```bash
./scripts/dc-up.sh
# apps/web  -> http://localhost:3300
# apps/api  -> http://localhost:8300/health

docker compose logs -f      # tail both apps' logs
docker compose down         # stop both (Supabase keeps running)
```

`./scripts/dc-up.sh` starts the local Supabase CLI stack (idempotent —
safe to run even if it's already up) and then `docker compose up -d`, so
it's the only command you need for a full local environment. Once
containers are up, plain `docker compose up -d` / `down` work too.

Builds once, then bind-mounts your source into both containers with
hot reload (`next dev` / `uvicorn --reload`) — edits on your machine take
effect immediately, no rebuild needed. `node_modules` lives in a named
Docker volume so `pnpm install` only reruns when `pnpm-lock.yaml` changes.
`apps/api/.env.local` points `DATABASE_URL`/`NEXT_PUBLIC_SUPABASE_URL` at
`host.docker.internal`, not `localhost`/`127.0.0.1`, so the api container
can reach the host-run Supabase stack.

This is separate from `scripts/local-dev/docker-compose.yml`, which only
spins up a bare Postgres for `pytest` (see Tests below).

### Alternative: run natively with pnpm/dev.sh

```bash
./dev.sh
# apps/web  -> http://localhost:3300
# apps/api  -> http://localhost:8300/health
```

Creates the apps/api virtualenv and installs workspace deps on first run
if missing. Ctrl-C stops both servers. Use this if you'd rather not run
Docker, or need to debug with tools that expect a native process.

## Run apps/web (Next.js)

```bash
pnpm --filter web dev --port 3300
# http://localhost:3300
```

## Run apps/api (FastAPI)

```bash
cd apps/api
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.local.example .env.local   # if present; otherwise create your own
uvicorn app.main:app --reload --port 8300
# http://localhost:8300/health
```

## Environment variables

Copy `.env.example` at the repo root and fill in real values for each app's
local `.env.local` (gitignored, never committed). See that file's comments
for what each variable is for.

## Local database + auth (real login)

`./dev.sh` alone gets you running servers, but `apps/web`'s login/signup
pages need a real Postgres + Supabase Auth (GoTrue) instance behind them.
Use the [Supabase CLI](https://supabase.com/docs/guides/cli):

```bash
brew install supabase/tap/supabase   # one-time
supabase start                       # starts local Postgres, GoTrue, Studio, etc.
```

This applies every migration in `supabase/migrations/` automatically and
prints the local API URL, DB URL, anon key, and service-role key. Copy
those into `apps/api/.env.local` and `apps/web/.env.local` (`NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`,
`SUPABASE_JWT_SECRET`) — then restart `./dev.sh` so both apps pick them up.
Supabase Studio (`http://127.0.0.1:54323` by default) gives you a UI over
the local DB and auth users. `supabase stop` shuts the stack down.

This is a separate stack from `scripts/local-dev/docker-compose.yml`
(bare Postgres on port 5434, no GoTrue) — that one exists only to give
`pytest` a fast, isolated database that mirrors CI's ephemeral Postgres
service; it's not meant for interactive use or real login flows.

## Design notes

- [`docs/parent_records_creation_timing.md`](docs/parent_records_creation_timing.md) — when a `parent_records` row gets created relative to signup vs. onboarding.
- [`docs/talent_profiles_cache_recompute.md`](docs/talent_profiles_cache_recompute.md) — how cached `talent_profiles` fields (completeness score, earnings, etc.) get recomputed.
- [`docs/stripe-minors-policy.md`](docs/stripe-minors-policy.md) — Stripe Connect's actual policy on account holders under 18, and an open product/legal question this surfaced (Teenure's own age gate is narrower than Stripe's Representative requirement) that needs sign-off before real (non-test-mode) Connect payouts go live for any Talent under 18.

## Tests

```bash
# apps/api — runs against scripts/local-dev/docker-compose.yml's bare
# Postgres (see apps/api/tests/conftest.py), not the Supabase CLI stack.
cd apps/api && source .venv/bin/activate && pytest

# apps/web
pnpm --filter web test       # unit tests, once wired up
pnpm --filter web test:e2e   # Playwright E2E (apps/web/tests-e2e)
```
