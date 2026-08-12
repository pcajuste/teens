# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This repository currently contains only the product/technical specification for Teenure — no application code has been written yet. The spec lives in `Teenure_MVP_Gameplan.md` (source of truth; `Teenure_MVP_Gameplan.docx` is a copy for non-technical stakeholders and should not be treated as authoritative).

Before writing any code in this repo, read `Teenure_MVP_Gameplan.md` in full. It is the spec, not background reading — it contains the exact database schema (Section 7), API routes (Section 8), and mandatory build sequence (Section 5, Section 10) that any implementation must follow.

## What Teenure is

A three-sided verified-achievement platform for high school students, with three user types: Rep (teen), Brand, and Recruiter (college/employer). The one-sentence product rule from the spec: "Teenure is a verified professional achievement record for teenagers. Every feature either adds to that record or it does not belong on the platform." Apply this rule when evaluating any proposed feature — see Section 1 and Section 1A ("Content Policy") for the enforced exclusions (no rep-to-rep messaging, no public feed, no profile photos, no dating/discovery mechanics).

## Mandatory build sequence

The spec requires this order, with each phase fully functional before the next begins (Section 5, Section 10):

1. Database schema (Section 7 — Postgres/Supabase, apply row-level security from the start) + FastAPI scaffolding
2. Phase 1: Rep Portal
3. Phase 2: Brand Portal
4. Phase 3: Recruiter Portal
5. Phase 4: Admin Portal

Do not skip ahead or build phases out of order.

## Intended stack (per Section 6 of the spec)

- Frontend: Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui
- Backend: FastAPI (Python 3.11+)
- Database/Auth/Storage: Supabase (Postgres, Supabase Auth, Supabase Storage)
- Payments: Stripe (campaign billing) + Stripe Connect (rep payouts)
- Email: Resend
- Hosting: Vercel (frontend) + Railway (FastAPI)
- Analytics: PostHog

Planned monorepo layout is `apps/web` (Next.js, route groups per portal: `(rep)`, `(brand)`, `(recruiter)`, `(admin)`) and `apps/api` (FastAPI, routers per domain: auth/reps/brands/campaigns/recruiters/payments/admin), with `packages/shared-types` for cross-boundary TypeScript types. None of this exists on disk yet — treat Section 6 of the spec as the layout to create, not to discover.

## Non-negotiable constraints (Section 9 and scattered throughout)

These are compliance/legal requirements, not style preferences — do not build around them:

- Hard age gate: under-13 blocked at signup; under-16 requires double opt-in parental consent (token-based, 72-hour expiry) before account activation
- FTC sponsorship disclosure checkbox required before a rep can accept any campaign
- Recruiter contact-credit deduction must happen server-side only, never client-side
- No passive behavioral tracking and no data collection beyond the fields in the Section 7 schema
- All financial calculations (platform fee splits, payouts) happen server-side; never trust client-submitted amounts
- Row-level security enabled on all Supabase tables from the first migration
- Intelligence-layer data must be anonymized and aggregated (minimum group size of 10) before any trend report — never derived from individual rep records
