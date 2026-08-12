# Campaign cancellation refund policy

Build Prompt 8 deliverable 6 required this to be flagged rather than
assumed, and left it explicitly unresolved. Build Prompt 10 owns the
actual Stripe refund call and, per its own deliverable text ("partial
refund for un-paid remainder when some reps already paid"), resolves
the open question below with a concrete, documented default rather
than leaving `refund_campaign` unimplemented indefinitely.

## What's implemented

`POST /brands/campaigns/:id/cancel` transitions the campaign to
`cancelled` from any of `draft`, `pending_payment`, `payment_failed`,
`active`, `paused` (see `campaigns_repository.CANCELLABLE_STATUSES`).
`completed` and `cancelled` itself are terminal and cannot be
re-cancelled.

For `draft`, `pending_payment`, and `payment_failed`, no Stripe charge
has ever succeeded (per the `campaign_status` enum's own comment: a
campaign only reaches `active` after `payment_intent.succeeded`), so
there is nothing to refund — cancellation is just the status
transition.

For `active` and `paused`, a real charge exists. The refund amount is:

```
refund_amount_cents = budget_cents - SUM(payout_cents
                        WHERE payout_status IN ('processing', 'paid'))
```

i.e. **the un-paid remainder of the budget is refunded**; any rep
payout already transferred (`processing`, meaning a Stripe Transfer
was already created) or completed (`paid`) is never clawed back. This
necessarily also refunds the slice of `platform_fee_cents`
attributable to the unpaid remainder — nothing was delivered for that
slice, so nothing is kept for it. The refund is issued via
`stripe_service.refund_campaign` (a partial `Refund` against the
campaign's `stripe_payment_intent_id`) only when the computed amount is
greater than zero; a `$0` refund call is skipped, since Stripe rejects
zero-amount refunds. The response reports both `refund_pending`
(whether a refund was actually issued) and the exact
`refund_amount_cents`.

## Decisions made, and what's still open

- **Reps `submitted`-but-not-yet-`confirmed` at cancellation time**: no
  payout is owed (`payout_status` is still `pending`), so their share
  is included in the refund. Cancelling does **not** force an
  immediate confirm/reject decision on open submissions — the
  `campaign_reps` row is left as-is; a brand can still confirm it after
  cancellation if they choose to pay for delivered work anyway (that
  path isn't blocked by this prompt, but isn't a documented flow
  either — flagged for a real product decision if this matters).
- **Reps still `invited`/`accepted` with no submission**: clearly no
  payout owed. Nothing here notifies them their invitation is now void
  — a pre-existing gap in every other cancellation-adjacent case in
  this codebase (no "campaign was cancelled" email exists anywhere),
  not something newly introduced by this decision.
- **Platform fee refundability**: resolved above (refunded
  proportionally to the unpaid remainder) — a deliberate choice, not
  the "non-refundable once charged" alternative some payment platforms
  use, because Teenure's platform fee is priced as a percentage of
  delivered campaign spend, not a flat processing fee.

This is the interim, documented default — not a claim that it's the
only defensible policy. A real product/legal review before this
handles non-test-mode money should confirm it, especially the platform
fee refund choice.
