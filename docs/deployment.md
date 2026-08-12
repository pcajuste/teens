# Deployment & CI/CD (Build Prompt 17)

Covers Section 6's target infra (Vercel + Railway + Supabase) and closes
out the gaps the build-log note in `Teenure_Build_Prompts.md` (the
"Build-log note (post-6A, pre-7)" under Prompt 18) flagged as still
outstanding when Prompt 17 was pulled forward early: lint step, Vercel/
Railway deploy config, staging environment, and documented rollback
procedure.

## 0. What already existed before this pass

`.github/workflows/ci.yml` was added ahead of schedule (see the Prompt 18
build-log note) and already covered, per PR on every push/PR to `main`:

- `api-tests` — pytest against a real ephemeral Postgres service, with
  every file in `supabase/migrations/*.sql` applied fresh first.
- `web-unit-tests` — `pnpm --filter web test` (Vitest).
- `web-build` — `pnpm build:web` (Next.js production build).
- `web-e2e` — Playwright smoke suite against the unauthenticated
  `/demo/rep` portal and public `/rep/*` pages (no backend).
- `web-e2e-auth` — Playwright against a real local Supabase CLI stack
  (`supabase start`) plus a live `apps/api` process, using CI-only
  placeholder secrets (`sk_test_ci`, `whsec_ci`, etc. — not real keys).

Not yet present before this pass: a lint job, and any of deliverables
2-6 below. Those are what this pass adds.

## 1. CI pipeline additions (this pass)

Added to `.github/workflows/ci.yml`:

- **`web-lint`** job — runs `pnpm lint` (`next lint`/ESLint) in
  `apps/web`, in its own job so a lint failure doesn't block/blend with
  the build or test signal in the PR checks list.
- **`web-build`** now also runs `pnpm exec tsc --noEmit` as an explicit
  typecheck step (matching `scripts/test-ci.sh`'s local equivalent),
  rather than relying only on `next build`'s incidental type checking.

No backend lint job was added: `apps/api/requirements.txt` and
`pyproject.toml` do not declare a lint tool (no `ruff`, `flake8`, or
`black` dependency exists anywhere in the repo). Adding one would be
inventing a tool the codebase hasn't adopted. **Gap, needs a human
decision:** pick a Python linter, add it to `requirements.txt`, and add
a `api-lint` CI job — out of scope for this pass per the "do not invent
commands that don't exist" constraint.

With this pass, every job in the workflow (`api-tests`,
`web-unit-tests`, `web-lint`, `web-build`, `web-e2e`, `web-e2e-auth`)
runs on every `pull_request` and returns non-zero on failure, so a
GitHub Actions check fails and (once branch protection is enabled, see
below) blocks merge.

### Branch protection (GitHub dashboard setting — not a repo file)

**Not yet enabled; needs a human with repo admin access.** In GitHub:
Settings -> Branches -> branch protection rule for `main` -> "Require
status checks to pass before merging" -> select all six CI jobs above.
This cannot be expressed as a committed file — it's account-level
GitHub configuration, not something `ci.yml` can set.

### Verifying a broken test actually blocks merge

**Not verified in this pass — marked TODO for a human.** Per this
task's explicit constraint, no broken-test commit was pushed to a
scratch branch. Searched `git log` and `docs/` for evidence this was
already exercised per Prompt 18's build-log note (which only claims the
*pipeline* was pulled forward, not that a broken-test-blocks-merge
drill was run) and `docs/test-coverage-report.md` (Prompt 16's
deliverable, no mention of a merge-blocking drill either) — no evidence
found either way.

**TODO (human, on a scratch branch, before relying on this in
production):**
1. Push a branch with one assertion flipped (e.g. `assert False` in any
   `apps/api/tests/test_*.py` file, or an `expect(...).toBe(...)` flip
   in a Vitest/Playwright spec).
2. Open a PR against `main`.
3. Confirm the corresponding CI job goes red and, once branch
   protection (above) is enabled, that GitHub refuses to allow the
   merge button to be pressed.
4. Close the PR and delete the scratch branch without merging.

## 2. Vercel config for apps/web

`apps/web/vercel.json` (added this pass):

```json
{
  "buildCommand": "cd ../.. && pnpm install --frozen-lockfile && pnpm build:web",
  "outputDirectory": ".next",
  "framework": "nextjs"
}
```

Vercel project settings (dashboard, not a file — set once when the
project is created):
- **Root Directory:** `apps/web` (monorepo — this is what makes the
  `cd ../..` in `buildCommand` land back at the repo root so the pnpm
  workspace lockfile is used).
- **Framework Preset:** Next.js (auto-detected once Root Directory is
  set; `vercel.json`'s `framework` key pins it explicitly).
- **Build Command / Output Directory:** as in `vercel.json` above
  (`pnpm build:web` == `pnpm --filter web build`, i.e. `next build`;
  output is Next's default `.next`).

### Env var mapping (Vercel project -> Environment Variables)

Source of truth for the full variable list is `.env.example` at the
repo root. Split by exposure:

**`NEXT_PUBLIC_*` — inlined into the client bundle at build time, safe
to expose:**
| Var | Notes |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Public Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Anon key — RLS enforces access, safe by design |
| `NEXT_PUBLIC_APP_URL` | Public URL of this Vercel deployment |
| `NEXT_PUBLIC_API_URL` | Public URL of the Railway-hosted `apps/api` (see below) |

**Server-only — read by Next.js server components/route handlers,
never sent to the browser. Must NOT be prefixed `NEXT_PUBLIC_` or they
leak client-side:**
| Var | Notes |
|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | Only if any `apps/web` server code uses it directly; if all privileged calls proxy through `apps/api`, this may not be needed in the web project at all — verify before setting it here, since granting it to `apps/web` widens the blast radius of a `apps/web` compromise unnecessarily |

All Stripe, Resend, `ADMIN_SECRET_KEY`, `JOBS_RUNNER_SECRET`,
`PARENT_SESSION_SECRET`, `EIN_ENCRYPTION_KEY`, and `DATABASE_URL`
belong to `apps/api` (Railway), not `apps/web` (Vercel) — `apps/web`
talks to those systems only through `apps/api`'s HTTP routes, per
Section 8. Do not set them in the Vercel project.

Set each var per Vercel Environment (Production / Preview /
Development) via the dashboard or `vercel env add <name> <environment>`
(Vercel CLI) — never commit real values to `vercel.json`, `.env`, or
any tracked file.

## 3. Railway config for apps/api

Railway is dashboard/CLI-driven for this repo; there is no
`railway.json`/`railway.toml` currently checked in, and this pass does
not invent one — service settings below are the ones to set in the
Railway dashboard when the service is created.

**Service settings:**
- **Root Directory:** `apps/api`
- **Build:** Railway's Nixpacks Python builder auto-detects
  `requirements.txt` and runs `pip install -r requirements.txt`. No
  Dockerfile exists in `apps/api/` — Nixpacks is the default path
  unless one is added later.
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  (matches `apps/api/app/main.py`'s app object and the `dev:api`/CI
  invocations already used elsewhere in the repo, adapted to Railway's
  injected `$PORT` instead of the hardcoded `8300`/`8000` used locally).
- **Health check path:** `/health` (`apps/api/app/routers/health.py`,
  already exercised by CI's `web-e2e-auth` job's readiness poll).

**Scheduled jobs:** `POST /internal/jobs/run/{job_name}`
(`apps/api/app/jobs/runner.py`) is invoked by a scheduler, not a
Railway-managed cron primitive in this codebase — set up a Railway Cron
Job (or an external scheduler hitting the route) that sends the
`JOBS_RUNNER_SECRET` header value. **Gap:** which job names need
scheduling and at what cadence isn't documented anywhere in this repo
yet — needs a human to enumerate `run/{job_name}` call sites and decide
a schedule per job.

**Secret injection:** every var in `.env.example` needed by `apps/api`
(`DATABASE_URL`, `SUPABASE_JWT_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`,
`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `RESEND_API_KEY`,
`ADMIN_SECRET_KEY`, `JOBS_RUNNER_SECRET`, `PARENT_SESSION_SECRET`,
`EIN_ENCRYPTION_KEY`, etc.) is **never committed** to this repo in any
form (not in `apps/api/.env.local`, which is gitignored, and not in any
Railway config file, since none is checked in). Real values are
injected exclusively via the Railway dashboard's service Variables tab,
or `railway variables set KEY=value` / `railway run` via the Railway
CLI, scoped per environment (staging vs. production — see  4 below).

## 4. Supabase migration-deploy step and ordering

`supabase/migrations/*.sql` is the single source of schema truth (CI's
`api-tests` job already applies every file in this directory in
filename order against its ephemeral Postgres, so filename ordering
must stay monotonic — this is an existing repo convention, not new).

**Deploy order (schema -> API -> web), and why:**

1. **Schema migration first.** Run `supabase db push` (Supabase CLI,
   authenticated against the target project via
   `supabase link --project-ref <ref>`) or apply
   `supabase/migrations/*.sql` directly with `psql` against the
   project's connection string. This must land *before* any API
   version that assumes the new columns/tables/RLS policies exist —
   an API deployed against an old schema is safe (older code doesn't
   know about new columns), but a schema deployed after new API code
   would break every request that touches the new shape.
2. **`apps/api` (Railway) second.** Railway redeploys on push to the
   tracked branch (or via `railway up`/a GitHub Action calling the
   Railway CLI). Only deploy once step 1's migration has been
   confirmed applied (Supabase dashboard's migration history, or
   `supabase migration list`).
3. **`apps/web` (Vercel) last.** Vercel redeploys on push to the
   tracked branch automatically once connected to the repo. Web is
   last because it's the layer most tolerant of being briefly behind
   (users see slightly-stale UI, not broken requests) and it depends
   on `apps/api`'s routes already being live at `NEXT_PUBLIC_API_URL`.

This ordering is currently a **manual runbook**, not automated: no
GitHub Actions deploy job exists in `.github/workflows/` (only `ci.yml`,
which tests but does not deploy). **Gap:** wiring `supabase db push` /
Railway deploy / Vercel deploy into an automated pipeline (e.g. a
`deploy.yml` triggered on merge to `main`, requiring `SUPABASE_ACCESS_TOKEN`,
`RAILWAY_TOKEN`, `VERCEL_TOKEN` as GitHub Actions secrets) is out of
scope for this pass — no cloud projects/tokens exist yet for it to
target (see  6 in the final report). Documenting the order here so
whoever wires the automation later encodes the same sequence.

### Rollback procedure

Because migrations run ahead of code, rollback runs in the *opposite*
order from deploy:

1. **Roll back `apps/web` (Vercel) first**, if the web deploy is the
   one implicated — Vercel dashboard -> Deployments -> pick the
   previous production deployment -> "Promote to Production" (instant,
   no rebuild). No migration interaction.
2. **Roll back `apps/api` (Railway) second**, if implicated — Railway
   dashboard -> Deployments -> redeploy the previous build. Since step
   1 above should already have any web-visible breakage covered,
   rolling back the API next restores request handling for both
   direct callers and web.
3. **Schema migrations are rolled back last, and only if truly
   necessary.** This repo's `supabase/migrations/` directory contains
   only forward migrations — no down-migrations exist. Prefer a
   **forward-fix migration** (write a new migration that undoes the
   problematic change) over reverting Supabase state, because:
   - Postgres schema changes can be destructive (dropped columns lose
     data) in a way redeploying old code is not.
   - Every environment (local dev, CI's ephemeral Postgres, staging,
     production) applies `supabase/migrations/*.sql` in filename
     order from scratch — inserting a true "down" migration file
     keeps that invariant; hand-editing Supabase state via the
     dashboard does not, and would drift local/CI schemas out of sync
     with production.
   - If data loss already occurred, restore from Supabase's
     point-in-time recovery / daily backups (dashboard: Database ->
     Backups) rather than attempting to hand-reconstruct rows.

## 5. Staging environment

Not yet provisioned (no cloud accounts exist for this repo per this
task's constraints) — documenting the intended setup:

- **Separate Supabase project** (not a branch of production): create a
  second Supabase project (e.g. `teenure-staging`), run
  `supabase link --project-ref <staging-ref>` from a separate local
  checkout or CI context, and apply every file in
  `supabase/migrations/` the same way production does. This gives
  staging its own Postgres instance, its own Supabase Auth user pool,
  and its own storage buckets — no shared state with production, so
  destructive staging testing (e.g. Prompt 16's parental-consent and
  age-gate flows creating throwaway accounts) can't touch real users.
- **Stripe test mode**, not a second Stripe account: Stripe's test mode
  is already the same account, toggled by using `sk_test_*`/`pk_test_*`
  keys instead of `sk_live_*`/`pk_live_*` — set `STRIPE_SECRET_KEY` and
  `STRIPE_PUBLISHABLE_KEY` in the staging Railway/Vercel environments to
  the test-mode keys. `STRIPE_WEBHOOK_SECRET` must be the signing
  secret for a **separate webhook endpoint** registered (in Stripe's
  dashboard, test mode) against the staging `apps/api` URL — reusing
  production's webhook secret would let staging traffic forge
  signatures indistinguishable from production's, or vice versa.
- **Railway and Vercel environments:** both platforms support named
  environments/environments-per-branch. Point a `staging` branch (or a
  Railway "staging" environment + a Vercel preview environment pinned
  to that branch) at the staging Supabase project's `DATABASE_URL` /
  `SUPABASE_*` keys and the Stripe test-mode keys above — never mix
  staging and production secrets in the same environment's variable
  set.
- **Resend:** either a sandboxed "from" address/domain not used in
  production, or Resend's test mode if the account has one, so staging
  emails (parental consent, magic links) don't originate from the
  production sending domain's reputation.

**Gap:** none of the above cloud resources exist yet (no Supabase
staging project, no Stripe webhook endpoint for it, no Railway/Vercel
staging environment) — this is a human/dashboard task, not something
achievable by adding repo files, and out of scope for this pass per
the "do not create actual cloud projects" constraint.

## 6. Full staging deploy + Prompt 16 integration-flow validation (description only)

Prompt 16 ("Testing Suite", commit `82a3473`) produced
`docs/test-coverage-report.md`, documenting a route-by-route audit of
every `apps/api/app/routers/*.py` endpoint against the pytest suite
(239 passing at that point) plus the acceptance criteria in
`Teenure_Build_Prompts.md`'s Prompt 16 section: integration flows
(campaign lifecycle, parental consent, parent-portal approval,
parent-blocked-category exclusion) passing end-to-end, and a frontend
test proving (not just visually confirming) that a parent-blocked
campaign is absent from the rendered available-campaigns panel.

A full staging validation, once  5's staging environment exists, would:

1. Apply `supabase/migrations/*.sql` to the staging Supabase project
   (step 1 of the deploy order in  4).
2. Deploy `apps/api` to the staging Railway environment pointed at that
   project, with `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET` set to
   Stripe test-mode values.
3. Deploy `apps/web` to a Vercel preview/staging environment pointed at
   the staging `apps/api` URL and staging Supabase anon key.
4. Re-run the same integration flows `docs/test-coverage-report.md`
   already exercises against local Postgres/CI (campaign lifecycle
   through to payout, parental consent double opt-in, parent-portal
   approve/block, blocked-category exclusion), but pointed at the
   staging URLs instead of `localhost` — i.e. Playwright's
   `test:e2e:auth` config (`apps/web/playwright.auth.config.ts`) with
   its `baseURL`/`NEXT_PUBLIC_API_URL` overridden to the staging
   deployment, plus a manual walkthrough of the Stripe test-mode
   payment/payout path (test-mode PaymentIntents and Connect transfers
   don't move real money, but do exercise the real Stripe API contract
   unlike anything mocked in `pytest`).
5. Confirm no `sk_live_`/production secret ever appears in staging logs
   or config (this pass's grep in the final report covers only the
   committed repo, not live log output — re-run an equivalent grep
   against Railway/Vercel deploy logs once staging exists).

**Not performed in this pass** — no staging environment exists yet to
validate against (dependent on  5's cloud provisioning, explicitly out
of scope here).

## 7. Secret scan (this pass)

Ran (repo root, excluding `node_modules/`, `.git/`, `.pnpm-store/`):

```
grep -rnE "sk_live_[A-Za-z0-9]|sk_test_[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC )?PRIVATE KEY-----|postgres(ql)?://[^ ]*:[^ ]*@" .
```

One match: `apps/api/tests/conftest.py:21` —
`"DATABASE_URL": "postgresql://teenure:teenure_dev_only@localhost:5434/teenure_test"`.
This is the documented local/CI test-database credential (matches
`teenure_dev_only`, the same placeholder password already visible in
`.github/workflows/ci.yml`'s `postgres` service block and
`apps/api/.env.local`'s comments) — a fixed, non-secret, `localhost`-only
value for the ephemeral test Postgres, not a real credential. No
`sk_live_*`, real `sk_test_*`, AWS access keys, or PEM private key
blocks were found anywhere in the repo.
