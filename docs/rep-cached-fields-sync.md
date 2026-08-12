# Keeping `rep_profiles` cached fields in sync

`rep_profiles.total_campaigns_completed`, `total_earnings_cents`,
`average_rating`, and `profile_completeness_score` are denormalized reads
computed from `campaign_reps` (the first three) and from the rep's own
profile fields (the last one).

## Decision: backend service-layer recompute, not a Postgres trigger

Chosen mechanism: a `recompute_rep_cache(rep_id)` function in
`app/services/` (implemented in Prompt 10, which is where the campaign
lifecycle transitions that affect these fields — `confirmed`, `paid`,
rating submission — actually happen), called synchronously at the end of
the request handler that causes the transition. Not a Postgres trigger.

**Why not a trigger:** `average_rating` and `total_earnings_cents` need to
be computed from application-level rules that are expected to evolve
(e.g. Prompt 10's rounding rule for fee splits, and any future change to
which `payout_status` values count toward "earnings"). Keeping that logic
in Python next to the rest of the payout/rating business logic — instead
of duplicated in PL/pgSQL — avoids two implementations of the same rule
drifting apart. A trigger is also harder to unit test than a plain Python
function, and Prompt 10's acceptance criteria require unit-testable fee
math.

**Why this still satisfies "keep it in sync":** every code path that
writes a `campaign_reps` transition affecting these fields (rep confirmed,
payout marked paid, rating submitted) already goes through
`app/services/payout_service.py` or the rating endpoint in
`app/routers/brands.py` (both server-side, both already re-authorizing
and recomputing money amounts per the ground rules in
`Teenure_Build_Prompts.md` §0) — so the same call site that changes the
source-of-truth row is the natural place to call `recompute_rep_cache`.
There is no path that mutates `campaign_reps` status/payout/rating
without going through the backend (RLS permits a rep or brand to write
to their own `campaign_reps` rows directly, but only to fields relevant
to their side of the flow — e.g. `submission_text`, `ftc_disclosure_accepted`
for the rep; `revision_note` for the brand — not `status`, `payout_cents`,
`brand_rating`, or `payout_status`, which the state-machine endpoints
control server-side. See Prompt 5/8/10's acceptance criteria).

**Profile completeness score** is simpler: it depends only on
`rep_profiles`' own columns, so it is recomputed inline whenever
`PUT /reps/me` writes an update (Prompt 5, deliverable 9) — no
cross-table read needed, so no separate job is required for it.

## Where this lives once implemented

- `app/services/rep_cache_service.py::recompute_rep_cache(rep_id)` (created in Prompt 10)
- Called from: `payout_service.release_payout()`, `POST /brands/campaigns/:id/reps/:rep_id/confirm`, `POST /brands/campaigns/:id/reps/:rep_id/rate`
- Profile completeness: computed inline in `PUT /reps/me` (Prompt 5)
