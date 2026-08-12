"""Payout engine: fee-split unit math plus Stripe Transfer initiation
and its webhook-driven completion (Build Prompt 10).

All financial math happens here, server-side only (Section 9) — never
trust a client-submitted amount, and never duplicate this math in
apps/web.

Distinct from app/services/campaign_service.py's
compute_campaign_fee_split, which runs once at campaign-creation time
and fixes payout_per_rep_cents (and therefore, once a rep is invited,
campaign_reps.payout_cents) on the campaign. By the time a payout is
released here, the per-rep amount has already been decided — this
module reads campaign_reps.payout_cents rather than recomputing a
split. calculate_platform_fee_split below exists for its own
Prompt-10-scoped unit-test coverage of the identical round-half-up rule
(the acceptance criterion asks for rounding coverage "at this layer"),
not because it's on release_payout's call path.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

from app.core.config import Settings
from app.repositories import campaign_milestones_repository, campaign_reps_repository, rep_profiles_repository
from app.services import stripe_service


def calculate_platform_fee_split(amount_cents: int, platform_fee_percent: int) -> tuple[int, int]:
    """Returns (platform_cut_cents, rep_payout_cents) for a gross
    amount. Same round-half-up rule as
    campaign_service.compute_campaign_fee_split: platform_cut_cents is
    (amount_cents * percent + 50) // 100, and rep_payout_cents is the
    exact remainder, so the two always sum back to amount_cents by
    construction."""
    if amount_cents < 0:
        raise ValueError("amount_cents must be >= 0")
    if not (0 <= platform_fee_percent <= 100):
        raise ValueError("platform_fee_percent must be between 0 and 100")
    platform_cut_cents = (amount_cents * platform_fee_percent + 50) // 100
    rep_payout_cents = amount_cents - platform_cut_cents
    return platform_cut_cents, rep_payout_cents


@dataclass(frozen=True, slots=True)
class PayoutResult:
    """outcome is one of:
    - "transferred": a new Stripe Transfer was created.
    - "already_processed": payout_status wasn't 'pending' -- a retried
      call, not an error. No second Transfer was created.
    - "not_confirmed": the row doesn't exist, isn't 'confirmed', or has
      no payout_cents set.
    - "rep_not_onboarded": the rep has no completed Stripe Connect
      account yet -- nothing to transfer to.
    """

    outcome: str
    campaign_rep: campaign_reps_repository.CampaignRep | None
    stripe_transfer_id: str | None = None


async def release_payout(conn: asyncpg.Connection, settings: Settings, campaign_rep_id: str) -> PayoutResult:
    """POST /brands/campaigns/:id/reps/:rep_id/confirm calls this right
    after campaign_reps_repository.confirm() succeeds (Build Prompt 10
    deliverable 4). Idempotent against a retried call: the confirm()
    state-machine guard (legal only from 'submitted') already prevents
    the router from reaching this twice for the same row under normal
    operation, and the payout_status='pending' check here is the second
    line of defense -- a retried call observes 'processing'/'paid' and
    returns "already_processed" rather than creating a second Transfer."""
    cr = await campaign_reps_repository.get_by_id(conn, campaign_rep_id)
    if cr is None or cr.status != "confirmed" or not cr.payout_cents:
        return PayoutResult(outcome="not_confirmed", campaign_rep=cr)
    if cr.payout_status != "pending":
        return PayoutResult(outcome="already_processed", campaign_rep=cr)

    rep = await rep_profiles_repository.get_by_id(conn, cr.rep_id)
    if rep is None or not rep.stripe_onboarding_complete or not rep.stripe_account_id:
        return PayoutResult(outcome="rep_not_onboarded", campaign_rep=cr)

    transfer_id = await stripe_service.create_payout_transfer(
        settings, stripe_account_id=rep.stripe_account_id, amount_cents=cr.payout_cents, campaign_rep_id=cr.id
    )
    updated = await campaign_reps_repository.set_payout_processing(conn, campaign_rep_id, stripe_transfer_id=transfer_id)
    if updated is None:
        # Lost a race with another release_payout call between the
        # payout_status check above and this UPDATE -- treat as already
        # processed rather than surfacing an error for what's actually
        # a successful transfer (by the winner of the race).
        return PayoutResult(outcome="already_processed", campaign_rep=cr, stripe_transfer_id=transfer_id)
    return PayoutResult(outcome="transferred", campaign_rep=updated, stripe_transfer_id=transfer_id)


async def admin_release_payout(
    conn: asyncpg.Connection, settings: Settings, campaign_rep_id: str, *, admin_id: str
) -> PayoutResult:
    """Admin-initiated manual release for a row sitting in the
    stuck-payments queue (Build Prompt 13 deliverable 3: "uses
    payout_service with admin-initiated audit flag"). Unlike
    release_payout above -- which is only ever legal from
    payout_status='pending' -- this is intentionally callable when
    payout_status is 'processing' (stuck > 48h, admin_repository's
    STUCK_PAYOUT_THRESHOLD_HOURS) or 'failed' (transfer.failed webhook),
    the two states that put a row in GET /admin/payments/stuck in the
    first place. Creates a fresh Stripe Transfer the same way
    release_payout does, then records the admin-initiated audit trail
    via admin_repository.mark_admin_released (who released it, when,
    and the new transfer id) -- never a silent retry indistinguishable
    from the automated path."""
    cr = await campaign_reps_repository.get_by_id(conn, campaign_rep_id)
    if cr is None or cr.status != "confirmed" or not cr.payout_cents:
        return PayoutResult(outcome="not_confirmed", campaign_rep=cr)
    if cr.payout_status not in ("processing", "failed"):
        return PayoutResult(outcome="already_processed", campaign_rep=cr)

    rep = await rep_profiles_repository.get_by_id(conn, cr.rep_id)
    if rep is None or not rep.stripe_onboarding_complete or not rep.stripe_account_id:
        return PayoutResult(outcome="rep_not_onboarded", campaign_rep=cr)

    transfer_id = await stripe_service.create_payout_transfer(
        settings, stripe_account_id=rep.stripe_account_id, amount_cents=cr.payout_cents, campaign_rep_id=cr.id
    )
    await admin_repository.mark_admin_released(conn, campaign_rep_id, admin_id=admin_id, stripe_transfer_id=transfer_id)
    updated = await campaign_reps_repository.get_by_id(conn, campaign_rep_id)
    return PayoutResult(outcome="transferred", campaign_rep=updated, stripe_transfer_id=transfer_id)


async def handle_transfer_paid(conn: asyncpg.Connection, stripe_transfer_id: str, *, at: datetime) -> None:
    """transfer.paid webhook. Marks the row 'paid' (both
    rep_campaign_status and payout_status) and recomputes the rep's
    cached rep_profiles totals (deliverable 7) -- see
    rep_profiles_repository.recompute_cached_totals's docstring for why
    that recompute happens here in application code rather than a DB
    trigger. Unknown transfer id or an already-'paid' row is a silent
    no-op -- not every Transfer in a Stripe account need be ours, and a
    duplicate webhook delivery must not double-count earnings."""
    cr = await campaign_reps_repository.get_by_stripe_transfer_id(conn, stripe_transfer_id)
    if cr is None:
        return
    updated = await campaign_reps_repository.set_payout_paid(conn, cr.id, at=at)
    if updated is None:
        return
    await rep_profiles_repository.recompute_cached_totals(conn, updated.rep_id)


async def release_milestone_payout(
    conn: asyncpg.Connection, settings: Settings, campaign_rep_milestone_id: str
) -> PayoutResult:
    """Per-milestone equivalent of release_payout above (Build Prompt 8B
    deliverable 8). Called right after
    campaign_milestones_repository.confirm succeeds -- from POST
    .../milestones/:milestone_id/confirm (brand-initiated) and from the
    milestone_auto_release job (rep_submission auto-confirm path).
    `campaign_rep` on the returned PayoutResult is deliberately still
    the campaign_reps.CampaignRep dataclass (the rep-identifying row),
    not a CampaignRepMilestone -- callers that only need to know
    "which rep got paid" (e.g. logging) don't need a second type; the
    milestone-specific row is available separately via
    campaign_milestones_repository.get_by_id if a caller needs it."""
    crm = await campaign_milestones_repository.get_by_id(conn, campaign_rep_milestone_id)
    if crm is None or crm.status != "confirmed" or not crm.payout_cents:
        return PayoutResult(outcome="not_confirmed", campaign_rep=None)
    if crm.payout_status != "pending":
        return PayoutResult(outcome="already_processed", campaign_rep=None, stripe_transfer_id=crm.stripe_transfer_id)

    cr = await campaign_reps_repository.get_by_id(conn, crm.campaign_rep_id)
    if cr is None:
        return PayoutResult(outcome="not_confirmed", campaign_rep=None)

    rep = await rep_profiles_repository.get_by_id(conn, cr.rep_id)
    if rep is None or not rep.stripe_onboarding_complete or not rep.stripe_account_id:
        return PayoutResult(outcome="rep_not_onboarded", campaign_rep=cr)

    transfer_id = await stripe_service.create_milestone_payout_transfer(
        settings,
        stripe_account_id=rep.stripe_account_id,
        amount_cents=crm.payout_cents,
        campaign_rep_id=cr.id,
        milestone_id=crm.campaign_milestone_id,
    )
    updated = await campaign_milestones_repository.set_payout_processing(
        conn, campaign_rep_milestone_id, stripe_transfer_id=transfer_id
    )
    if updated is None:
        # Lost a race with another release_milestone_payout call --
        # same "treat as already processed" logic as release_payout's
        # own race guard above.
        return PayoutResult(outcome="already_processed", campaign_rep=cr, stripe_transfer_id=transfer_id)
    return PayoutResult(outcome="transferred", campaign_rep=cr, stripe_transfer_id=transfer_id)


async def handle_transfer_paid_milestone(conn: asyncpg.Connection, stripe_transfer_id: str, *, at: datetime) -> None:
    """transfer.paid webhook, metadata.payment_type == 'milestone'
    branch (Build Prompt 8B deliverable 9). Unknown transfer id or an
    already-'paid' row is a silent no-op, same rationale as
    handle_transfer_paid above."""
    crm = await campaign_milestones_repository.get_by_stripe_transfer_id(conn, stripe_transfer_id)
    if crm is None:
        return
    updated = await campaign_milestones_repository.set_payout_paid(conn, crm.id, at=at)
    if updated is None:
        return
    await campaign_milestones_repository.bump_campaign_rep_milestone_totals(conn, crm.campaign_rep_id)
    cr = await campaign_reps_repository.get_by_id(conn, crm.campaign_rep_id)
    if cr is not None:
        await rep_profiles_repository.recompute_cached_totals(conn, cr.rep_id)


async def handle_transfer_failed_milestone(
    conn: asyncpg.Connection, stripe_transfer_id: str
) -> campaign_milestones_repository.CampaignRepMilestone | None:
    """transfer.failed webhook, metadata.payment_type == 'milestone'
    branch. No dedicated milestone-payment-failure admin queue exists
    beyond `WHERE payout_status = 'failed'` on campaign_rep_milestones
    -- same interim-queue rationale as handle_transfer_failed above."""
    crm = await campaign_milestones_repository.get_by_stripe_transfer_id(conn, stripe_transfer_id)
    if crm is None:
        return None
    return await campaign_milestones_repository.set_payout_failed(conn, crm.id)


async def handle_transfer_failed(conn: asyncpg.Connection, stripe_transfer_id: str) -> campaign_reps_repository.CampaignRep | None:
    """transfer.failed webhook: payout_status -> 'failed'. No admin
    queue table exists yet (Prompt 13 builds the Admin Portal) -- until
    then, `WHERE payout_status = 'failed'` on campaign_reps is that
    queue, flagged here rather than inventing a table this prompt
    doesn't own. Returns the updated row (or None if unknown/already
    handled) so the webhook handler can log/alert on it."""
    cr = await campaign_reps_repository.get_by_stripe_transfer_id(conn, stripe_transfer_id)
    if cr is None:
        return None
    return await campaign_reps_repository.set_payout_failed(conn, cr.id)
