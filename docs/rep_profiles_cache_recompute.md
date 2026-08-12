# rep_profiles cached-field recompute strategy (design note)

Deliverable 4 of Build Prompt 2 asks for a design note, not shipped
trigger code — this repo is still pre-Phase-1, so the events that would
drive these fields (payouts, ratings, profile edits) don't exist as
application code yet. Documenting the approach now so Prompt 5+
(Rep Portal backend) and Prompt 10 (Payout Engine) implement against an
agreed design rather than inventing one ad hoc.

## Fields in question

`public.rep_profiles`:
- `total_campaigns_completed` (INTEGER)
- `total_earnings_cents` (INTEGER)
- `average_rating` (NUMERIC(3,2))
- `profile_completeness_score` (INTEGER 0-100)

## Recommended strategy: AFTER-trigger on campaign_reps, not a scheduled job

Three of the four fields (`total_campaigns_completed`,
`total_earnings_cents`, `average_rating`) are pure aggregates over
`campaign_reps` rows for a given `rep_id`. They should be recomputed
synchronously, inside the same transaction that changes the underlying
`campaign_reps` row, via a Postgres trigger — not a periodic batch job.
Reasons:

1. **Financial correctness.** `total_earnings_cents` feeds the parent
   dashboard (Section 9A) and any future payout summaries. A batch job
   with a recompute lag creates a window where a rep/parent sees stale
   earnings right after a payout — avoidable with a synchronous trigger
   at negligible cost (campaign completion/payout events are low
   frequency per rep, not high-volume writes).
2. **Section 9's server-side-only financial rule.** Computing the
   aggregate in the database, from the authoritative `campaign_reps`
   rows, rather than having the API compute-and-write it, removes an
   entire class of client/API drift bugs (the API could otherwise write
   an incorrect cached value from stale state).

### Trigger shape (to implement in a later Prompt, not this one)

```sql
CREATE OR REPLACE FUNCTION public.recompute_rep_profile_cache() RETURNS TRIGGER AS $$
DECLARE
  target_rep_id UUID := COALESCE(NEW.rep_id, OLD.rep_id);
BEGIN
  UPDATE public.rep_profiles rp
  SET
    total_campaigns_completed = agg.completed_count,
    total_earnings_cents      = agg.earnings_cents,
    average_rating            = agg.avg_rating,
    updated_at                = now()
  FROM (
    SELECT
      COUNT(*) FILTER (WHERE status = 'paid')                         AS completed_count,
      COALESCE(SUM(payout_cents) FILTER (WHERE payout_status = 'paid'), 0) AS earnings_cents,
      ROUND(AVG(brand_rating) FILTER (WHERE brand_rating IS NOT NULL), 2)  AS avg_rating
    FROM public.campaign_reps
    WHERE rep_id = target_rep_id
  ) agg
  WHERE rp.id = target_rep_id;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE TRIGGER trg_campaign_reps_recompute_rep_cache
AFTER INSERT OR UPDATE OF status, payout_status, payout_cents, brand_rating OR DELETE
ON public.campaign_reps
FOR EACH ROW
EXECUTE FUNCTION public.recompute_rep_profile_cache();
```

`SECURITY DEFINER` is required because a rep's own RLS-scoped connection
should not need direct UPDATE rights on every other rep's aggregate
during unrelated writes — the trigger runs with the owning function's
privileges, not the caller's.

## `profile_completeness_score`: recompute on rep_profiles write, not campaign_reps

This field depends only on `rep_profiles` columns themselves (is `bio`
filled in, are social handles present, is `school_type` set, etc.), so
it belongs on a `BEFORE UPDATE OF <profile columns> ON rep_profiles`
trigger that recomputes the score from `NEW.*` before the row is
written — cheaper than a scheduled job and avoids a second UPDATE
statement (and therefore a second `updated_at` bump) after the fact.

## Why not a scheduled job for any of these

A nightly/hourly recompute job (`app/jobs/`, per the existing Prompt 1
scaffolding) was considered and rejected as the *primary* mechanism:
it would either run too infrequently (stale financial data visible to
reps/parents) or, run frequently enough to avoid that, cost more total
compute than trigger-per-write for the data volumes expected pre-scale.
A low-frequency **reconciliation** job (e.g. nightly) is still worth
adding once Prompt 10's payout engine exists, purely as a drift-repair
safety net against any bug in the trigger path — not as the source of
truth.
