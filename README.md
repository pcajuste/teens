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

## Run apps/web (Next.js)

```bash
pnpm --filter web dev
# http://localhost:3000
```

## Run apps/api (FastAPI)

```bash
cd apps/api
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.local.example .env.local   # if present; otherwise create your own
uvicorn app.main:app --reload --port 8000
# http://localhost:8000/health
```

## Environment variables

Copy `.env.example` at the repo root and fill in real values for each app's
local `.env.local` (gitignored, never committed). See that file's comments
for what each variable is for.

## Tests

```bash
# apps/api
cd apps/api && source .venv/bin/activate && pytest

# apps/web
pnpm --filter web test   # once a test runner is wired up (later prompt)
```
