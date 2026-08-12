# Compliance Checklist — Section 9 Audit (Build Prompt 15)

Dedicated audit pass against `Teenure_MVP_Gameplan.md` Section 9 (Legal and
Compliance) and Section 9A (Parent Portal compliance notes). This does not
add features — it verifies and records enforcement that already exists, and
names what's still open.

Full backend test suite as of this audit: **217 passed** (`cd apps/api && pytest`).

---

## 1. Age gate

**Requirement:** Hard block at under-13. DOB collected and validated server-side, not client-side.

- **Implementing code:** [`apps/api/app/routers/auth.py:57-137`](../apps/api/app/routers/auth.py) (`signup`) computes age from `body.date_of_birth` using server clock (`date.today()`), never a client-submitted age. Pure age math isolated in [`apps/api/app/core/age.py:10-14`](../apps/api/app/core/age.py) (`compute_age`). Minimum age threshold is `settings.min_rep_age`, read from server config, not request body.
- **Covering test(s):** `test_signup_age_12_returns_400_and_creates_no_row` (`apps/api/tests/test_auth.py:34`) — asserts 400 `age_not_permitted` *and* that no `public.users` row is created, so a rejected signup can't leave a partial account behind.
- **Status:** **Implemented.**

## 2. Parental consent (under-16)

**Requirement:** Double opt-in email flow. 72-hour token expiry, single-use.

- **Implementing code:** [`apps/api/app/routers/auth.py:46`](../apps/api/app/routers/auth.py) `CONSENT_TOKEN_TTL = timedelta(hours=72)`; token issued at signup via `secrets.token_urlsafe(32)`; verified in the `/auth/parent-verify/{token}` handler, which checks `issued_at` against the TTL and calls `mark_parent_verified_and_activate` (`apps/api/app/repositories/users_repository.py`), which is the single-use gate — it activates the account and the token cannot verify a second time.
- **Covering test(s):**
  - `test_parent_verify_activates_account` (`test_auth.py:91`) — happy path.
  - `test_parent_verify_token_used_twice_returns_already_used` (`test_auth.py:101`) — reuse-after-activation, 400 `token_already_used`.
  - `test_parent_verify_expired_token_returns_expired` (`test_auth.py:113`) — backdates `consent_token_issued_at` by 73 hours, asserts 400 `token_expired`.
  - `test_resend_consent_sends_new_email_and_rotates_token` (`test_auth.py:135`) — old token invalidated on rotation.
- **Status:** **Implemented.** Reuse-after-activation (the specific scenario Prompt 15 calls out) is directly tested.

## 3. FTC disclosure

**Requirement:** No submission path — including admin override — can produce a `submitted` `campaign_reps` row without `ftc_disclosure_accepted = TRUE`.

- **Implementing code:**
  - Rep-facing gate: [`apps/api/app/routers/reps.py:556`](../apps/api/app/routers/reps.py) — `submit_campaign` raises 403 `ftc_disclosure_required` if `not cr.ftc_disclosure_accepted`. This is the real enforcement point (submission time), not just the acceptance-step checkbox.
  - Admin force-resolve: [`apps/api/app/routers/admin.py:230`](../apps/api/app/routers/admin.py) — `resolve_campaign` skips any row where `not cr.ftc_disclosure_accepted`, even under admin force-confirm, with an explicit comment that no code path (including this one) may bypass the gate.
- **Covering test(s):** `apps/api/tests/test_reps_portal.py` (submission gate), `apps/api/tests/test_admin_portal.py` (force-resolve skip behavior for undisclosed rows).
- **Status:** **Implemented.**

## 4. Parent campaign approval gate

**Requirement:** No rep can accept a campaign requiring parent approval without a recorded approval. RLS policy (Prompt 2) and API check (Prompt 5) must enforce this **independently**.

- **Implementing code:**
  - RLS: [`supabase/migrations/20260811210400_rls.sql:80-92`](../supabase/migrations/20260811210400_rls.sql) — `rls.rep_can_see_campaign()` returns TRUE only when `parent_approval_status IN ('not_required', 'approved')`.
  - API: [`apps/api/app/routers/reps.py:488-499`](../apps/api/app/routers/reps.py) — `accept_campaign` returns 403 `awaiting_parent_approval` / `parent_blocked` independent of the RLS layer.
- **Covering test(s):** `test_accept_blocked_awaiting_parent_approval` (`test_reps_portal.py:323`) exercises the API-layer gate end-to-end.
- **Status:** **Partial.** The API-layer check is directly tested and passing. The RLS policy itself is *not* independently exercised by the test suite: `apps/api/tests/conftest.py` connects to Postgres as the table-owning role (`teenure` — see `DATABASE_URL` at `conftest.py:21`), and Postgres table owners bypass RLS by default (the migration does not set `FORCE ROW LEVEL SECURITY`). In production, Supabase's `authenticated`/`anon` roles are non-owners so the policy applies — but nothing in this repo proves it. **To close:** add a test that connects as a non-owner role (or `SET ROLE` to one) with `request.jwt.claims` set to a rep's JWT, and asserts a direct `SELECT` against `campaigns` cannot see a row while `parent_approval_status = 'pending'`. This requires creating a non-owner Postgres role locally, which doesn't exist yet in the migrations (only the JWT-claim shim functions in `20260811210000_extensions_and_auth_shim.sql`).

## 5. Data minimization

**Requirement:** Collect only fields listed in Section 7. No passive behavioral tracking, no third-party enrichment.

- **Method:** Compared every response schema in `apps/api/app/schemas/*.py` against the Section 7 table definitions (`Teenure_MVP_Gameplan.md:552-802`) and the `intelligence_events_anonymized` table added by Prompt 14.
- **Findings:**
  - All rep/brand/recruiter/parent/admin response models expose fields traceable to Section 7 columns; no ad hoc analytics, device, or location fields beyond `rep_profiles.city`/`state` were found.
  - `public.intelligence_events_anonymized` (`supabase/migrations/20260817090000_intelligence_layer.sql`) is additive beyond Section 7 but is explained and justified in-migration (Section 3.5/Section 9 intelligence pipeline) and is structurally non-identifying — no FK column of any kind exists on the table (proven by `test_anonymized_table_has_no_identifying_join_path` and `test_anonymized_table_has_no_foreign_keys` in `apps/api/tests/test_intelligence.py`). This is scope growth under an explicit spec section, not undocumented data collection.
- **Status:** **Implemented.** No unlisted/unjustified PII fields found in a manual schema diff. This was a manual review, not an automated test — see "what's needed to close" below if a lint-style guard is wanted.
- **What would make this stronger (not currently open, just a suggestion):** a CI check that fails if a schema class gains a field with no corresponding Section 7 column and no comment justifying it, so drift doesn't require another manual pass later.

## 6. Stripe Connect minors

**Requirement:** Research Stripe's policy on Connected Accounts for under-18 before launch; may require parent as account holder.

- **Decision doc:** [`docs/stripe-minors-policy.md`](stripe-minors-policy.md) — already written, cites Stripe Services Agreement §1.2(b) (minimum account age 13), documents that under-18 triggers Stripe's own hosted-onboarding "Representative" requirement rather than something Teenure's code special-cases.
- **Status:** **Open — explicitly flagged as a launch blocker in the source doc itself**, not just by this audit. `docs/stripe-minors-policy.md` (lines ~71-80) identifies an unresolved gap: Teenure's own age gate lets 16-17-year-olds sign up and use the platform independently (no parental consent required at that age per this repo's `parental_consent_required_under` threshold), but Stripe's Representative requirement applies to *everyone* under 18 — so those reps will hit an unresolved UX/legal question the first time they reach Connect payout onboarding. **To close:** product/legal decision on how a 16-17-year-old rep completes Connect onboarding (e.g., require a parent as Representative at that step even though Teenure's own consent gate didn't require it at signup), then implement the resulting flow.

## 7. Anonymization pipeline

**Requirement:** Re-run Prompt 14's acceptance tests; do not assume they still pass.

- **Re-run result:** All intelligence-layer tests pass as part of the full-suite run (217 passed), including:
  - `test_anonymized_table_has_no_identifying_join_path` / `test_anonymized_table_has_no_foreign_keys` — structural non-reidentifiability.
  - `test_write_job_strips_all_pii` — write path never persists rep_id/campaign_id/user_id.
  - `test_group_below_ten_returns_insufficient_sample_size` / `test_group_at_or_above_ten_returns_real_numbers` — minimum-group-size-of-10 gate (`MIN_GROUP_SIZE = 10`, `apps/api/app/repositories/intelligence_repository.py:26`).
  - `test_null_school_type_buckets_to_unspecified_and_is_still_gated` — the `unspecified` bucket doesn't get a free pass around the size gate.
  - `test_non_admin_roles_cannot_read_trend_reports` / `test_unauthenticated_cannot_read_trend_reports` — access control on the read side.
- **Status:** **Implemented.** All named tests currently pass.

## 8. Parent portal data scope (monthly digest)

**Requirement:** Digest must never include recruiter message content, submission text/files, or brand contact details.

- **Implementing code:** [`apps/api/app/services/parent_service.py:110-146`](../apps/api/app/services/parent_service.py) `send_digest_email` — structurally cannot leak this content: it only calls `campaign_reps_repository.monthly_digest_stats` (returns counts/sums/category list) and rep-profile context (name, earnings, completeness score). It never queries `recruiter_contacts` or `campaign_reps.submission_text`/`submission_file_urls` at all, so there's no code path by which that data could reach the email template.
- **Covering test:** `test_monthly_digest_job_excludes_recruiter_and_submission_content` (`apps/api/tests/test_parent_portal.py:297`) asserts the rendered email HTML excludes the forbidden terms.
- **Status:** **Implemented, with a noted test weakness.** The current test only proves the template has no hardcoded leak — the seed helper (`seed_rep_with_parent` in `conftest.py`) never creates a `recruiter_contacts` row or a `campaign_reps.submission_text` value in the first place, so the negative assertion isn't exercised against real data that could have leaked. The architectural guarantee above (no query touches those tables) is the stronger evidence here. **To fully close:** extend the test to seed a recruiter message and a submission with distinctive marker strings, then assert those exact strings are absent from the sent email — proving the boundary against real data, not just against the query's own field list.

## 9. Privacy policy / ToS / CPPA — technical facts inventory

Per Prompt 15 item 9, this is not a policy document — it is the list of technical facts the eventual lawyer-reviewed privacy policy and ToS must accurately describe, sourced from what's actually implemented:

- **What's collected, per role:**
  - Rep: email, password (hashed via Supabase Auth), date of birth, parent email (if under 16), display name, school name, school type, city, state, graduation year, bio, category tags, Instagram/TikTok handles, campaign submission text/files, banking details via Stripe Connect (not stored in Teenure's own DB — see `stripe_connect_columns` migration, which stores only Stripe account IDs).
  - Brand: company name, website, EIN, industry, target categories, Stripe customer ID.
  - Recruiter: institution name/type, website, Stripe customer/subscription IDs.
  - Parent: email only (`parent_records.parent_email`) — parents have no `auth.users` account (Section 9A).
- **Why each field is collected:** every field above traces to a Section 7 column with a specific product purpose (matching, disclosure, payout, verification); no field exists purely for analytics/tracking. No passive behavioral tracking is implemented anywhere in `apps/api`.
- **Retention:** not currently defined anywhere in code or migrations — **fact for the lawyer-reviewed policy to fill in, currently undetermined at the implementation level.**
- **Who sees what:**
  - Recruiters see rep profile data only for reps who set `recruiter_visible = TRUE`, gated by RLS policy `"Recruiters see opted-in reps"` (`20260811210400_rls.sql:122`).
  - Brands see rep data only via campaign context (`"Brands see reps via campaign context"`, `20260811210400_rls.sql:133`), not platform-wide.
  - Intelligence-layer consumers (Stream Two subscribers) see only aggregated, anonymized, minimum-group-10 data — never individual rep records (Section 9 Data Architecture Constraint; see item 7 above).
- **Minor-specific rights / parent rights:**
  - Under-16 signup requires parent consent before activation (item 2).
  - Parents get a dedicated portal (Section 9A) with approve/block on any campaign, values filters, digest opt-in/out, and suspend/unsuspend — all parent-initiated actions are reversible only by the parent, admin-initiated ones only by admin (per `docs/` and `apps/api/app/routers/parent.py`).
  - Parent portal access expires at the rep turning 18 (`parent_records.portal_expires_at`), checked at every session verification, not just at record creation.
- **No selling of minor data, no targeted advertising using minor data:** consistent with current implementation — no ad-tech integration, no third-party data-sharing code exists anywhere in `apps/api`.
- **Status:** **Partial — informational deliverable, not a code gap.** The facts above are accurate as of this audit and ready to hand to a privacy lawyer. Retention policy is the one concrete unresolved item (not yet decided anywhere in the codebase or docs) and should be decided before the policy is drafted, not derived from code that doesn't exist yet.

---

## Summary

| # | Requirement | Status |
|---|---|---|
| 1 | Age gate | Implemented |
| 2 | Parental consent (72h/single-use) | Implemented |
| 3 | FTC disclosure (incl. admin override) | Implemented |
| 4 | Parent approval gate (RLS + API) | Partial — RLS policy untested independently of the API layer |
| 5 | Data minimization | Implemented (manual review) |
| 6 | Stripe Connect minors | Open — launch blocker, self-flagged in `docs/stripe-minors-policy.md` |
| 7 | Anonymization pipeline | Implemented |
| 8 | Parent portal digest content scope | Implemented, test could be strengthened with seeded negative data |
| 9 | Privacy policy technical facts | Partial — retention policy undecided |

**Open items requiring a decision before launch:**
1. Stripe Connect minors: how a 16-17-year-old rep completes Connect payout onboarding (item 6).
2. Data retention policy — not yet defined at the implementation level (item 9).

**Test-coverage gaps worth closing (not launch blockers, but named per Prompt 15's audit standard):**
1. Independent RLS-level test for the parent-approval gate (item 4).
2. Digest-exclusion test with seeded recruiter/submission data instead of a template-only check (item 8).
