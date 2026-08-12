# parent_records creation timing (design note)

Resolves a conflict surfaced while implementing Build Prompt 4 (Auth
Flows) between `Teenure_Build_Prompts.md`'s Prompt 4 deliverable text
and `Teenure_MVP_Gameplan.md` Section 7's schema comments (the
authoritative spec per CLAUDE.md). Documenting the resolution here so
Prompt 5 (Rep Portal — Backend) implements against an agreed design
rather than re-discovering the conflict.

## The conflict

`Teenure_Build_Prompts.md` Prompt 4 says the 16-17 signup path should
"create parent_record with parent_email if provided, digest_enabled =
true, campaign_approval_required = true by default." But
`Teenure_MVP_Gameplan.md` Section 7's `parent_records` comment (already
verbatim in `supabase/migrations/20260811210200_core_tables.sql`) says
the opposite: a 16-17 rep gets **no** `parent_records` row unless a
parent separately claims one (explicitly out of scope for MVP) — such
reps simply have `campaign_approval_required` permanently `FALSE` with
no row at all.

There's also a hard structural blocker regardless of which text wins:
`parent_records.rep_id` is a `NOT NULL UNIQUE` FK to `rep_profiles.id`,
and `rep_profiles` rows aren't created until the rep completes
onboarding (Prompt 5, Phase 1). No `parent_records` row can be inserted
at `/auth/signup` or `/auth/parent-verify/:token` time (Prompt 4) —
`rep_profiles` doesn't exist yet at either point.

## Resolution

`Teenure_MVP_Gameplan.md` is the source of truth (CLAUDE.md). Section
7's schema comment governs:

- **Under-16 signup (consent-flow path):** Prompt 4 stores
  `parent_email`, `consent_token`, `consent_token_issued_at` on
  `public.users` and, on successful `/auth/parent-verify/:token`, sets
  `parent_verified_at` and flips `account_status` to `active`. It does
  **not** create a `parent_records` row — it can't yet.
- **16-17 signup:** no `parent_email` requirement, no consent flow, no
  `parent_records` row ever created automatically. Matches Section 7
  exactly.
- **Prompt 5 (Rep Portal — Backend)** is responsible for creating the
  `parent_records` row, at the point `rep_profiles` is created during
  onboarding, **only** for reps whose `public.users.parent_verified_at
  IS NOT NULL** (i.e. reps who went through the under-16 consent flow).
  It seeds `parent_email` from `public.users.parent_email`,
  `campaign_approval_required = TRUE`, `digest_enabled = TRUE`, and
  `portal_expires_at` = the rep's 18th birthday, per Section 7.
- 16-17 reps get no `parent_records` row from this flow, consistent
  with Section 7. A parent "separately claiming" a 16-17 rep's record
  is explicitly out of scope for MVP.

This avoids altering the `parent_records.rep_id` FK (which nothing
depends on yet, but changing it would contradict Section 7's verbatim
schema for no real gain) and avoids inventing a placeholder
`rep_profiles` row at signup just to satisfy the FK early.
