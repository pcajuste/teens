"""Stripe webhook handler (Build Prompt 7 deliverable 5, completed by
Build Prompt 10). Single endpoint, dispatch table keyed by event type,
per Section 8:

    payment_intent.succeeded          -> activate campaign
    payment_intent.payment_failed     -> notify brand, revert campaign
    transfer.paid                     -> update payout_status 'paid'
    transfer.failed                   -> alert admin, flag for review
    customer.subscription.created     -> activate recruiter account (Prompt 11)
    customer.subscription.renewed     -> reset contact credits     (Prompt 11)
    customer.subscription.deleted     -> downgrade recruiter account (Prompt 11)

account.updated (Prompt 7), payment_intent.*/transfer.* (Prompt 10) are
implemented; customer.subscription.* stay registered no-op stubs so an
event Stripe sends before Prompt 11 lands returns 200 (telling Stripe
not to retry) instead of 404/500. Signature verification happens before
any dispatch, and a bad signature never reaches business logic
(Section 8 acceptance criterion) -- see stripe_service.verify_webhook_signature.

Idempotency (Build Prompt 10 acceptance criterion: "same webhook
payload twice -> no duplicate side effects"): every event id is
recorded in stripe_events (insert-or-skip, see
app/repositories/stripe_events_repository.py) before dispatch. A
retried delivery of an event already recorded returns 200 without
calling its handler again."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Awaitable, Callable

import asyncpg
import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.db.pool import get_connection
from app.repositories import (
    brand_profiles_repository,
    campaigns_repository,
    exclusivity_repository,
    recruiter_profiles_repository,
    rep_profiles_repository,
    stripe_events_repository,
    users_repository,
)
from app.services import payout_service, stripe_service
from app.services.email_service import (
    send_campaign_payment_failed_email,
    send_exclusivity_purchase_confirmed_email,
    send_exclusivity_purchase_failed_email,
)
from app.services.resend_client import ResendClient, resend_client_dependency

import logging

_logger = logging.getLogger("teenure.webhooks.exclusivity")

router = APIRouter(tags=["webhooks"])

# Every handler takes the same four args -- conn/event plus settings/
# resend_client, even the ones (like _handle_account_updated) that
# don't need the latter two -- so the dispatch table stays a flat,
# uniform mapping rather than needing per-entry argument-shape logic.
Handler = Callable[[asyncpg.Connection, "stripe.Event", Settings, ResendClient], Awaitable[None]]


async def _handle_account_updated(conn: asyncpg.Connection, event: "stripe.Event", settings: Settings, resend_client: ResendClient) -> None:
    account = event["data"]["object"]
    profile = await rep_profiles_repository.get_by_stripe_account_id(conn, account["id"])
    if profile is None:
        # Not one of our rep Connect accounts (or the account row hasn't
        # been written yet in a race with the onboarding request) --
        # nothing to update, and not an error worth rejecting the
        # webhook over.
        return

    # account is a stripe.StripeObject -- supports __getitem__/`in` but
    # not dict's .get(), which its __getattr__ override routes into a
    # failed __getitem__ lookup instead of falling back to None.
    onboarding_complete = bool(account["charges_enabled"] if "charges_enabled" in account else False) and bool(
        account["payouts_enabled"] if "payouts_enabled" in account else False
    )
    if onboarding_complete != profile.stripe_onboarding_complete:
        await rep_profiles_repository.set_stripe_onboarding_complete(conn, profile.id, onboarding_complete)


async def _handle_payment_intent_succeeded(conn: asyncpg.Connection, event: "stripe.Event", settings: Settings, resend_client: ResendClient) -> None:
    """Build Prompt 10 deliverable 3: 'pending_payment' -> 'active'.
    Unknown PaymentIntent id (not ours, or the campaign row hasn't been
    written yet) or a campaign not currently 'pending_payment' (e.g. a
    replayed event after cancellation) is a silent no-op.

    Build Prompt 11 deliverable 7: a recruiter credit top-up is also a
    PaymentIntent, tagged via metadata (stripe_service.create_credit_topup_payment_intent)
    since campaigns and credit purchases share this one webhook
    endpoint/event type -- checked first, since a top-up PaymentIntent
    id never matches a campaign row."""
    intent = event["data"]["object"]

    if "metadata" in intent and "type" in intent["metadata"] and intent["metadata"]["type"] == "recruiter_credit_topup":
        metadata = intent["metadata"]
        recruiter_id = metadata["recruiter_id"] if "recruiter_id" in metadata else None
        credits = int(metadata["credits"]) if "credits" in metadata else 0
        if recruiter_id and credits > 0:
            await recruiter_profiles_repository.add_credits(conn, recruiter_id, credits=credits)
        return

    if "metadata" in intent and "type" in intent["metadata"] and intent["metadata"]["type"] == "category_exclusivity":
        await _handle_exclusivity_payment_succeeded(conn, intent, resend_client)
        return

    campaign = await campaigns_repository.get_by_stripe_payment_intent_id(conn, intent["id"])
    if campaign is None:
        return
    await campaigns_repository.set_active(conn, campaign.id)


async def _handle_exclusivity_payment_succeeded(conn: asyncpg.Connection, intent, resend_client: ResendClient) -> None:
    """Build Prompt 8C deliverable 4: payment_intent.succeeded ->
    payment_status='paid', brand confirmation email, admin audit log.
    Unknown PaymentIntent id (not ours yet, or a race with the
    purchase-row insert) is a silent no-op, matching this file's other
    handlers' precedent."""
    agreement = await exclusivity_repository.get_by_payment_intent_id(conn, intent["id"])
    if agreement is None:
        return
    updated = await exclusivity_repository.mark_paid(conn, agreement.id)
    if updated is None:
        # Already 'paid' -- a retried webhook delivery for the same
        # event id never reaches here twice (stripe_events_repository
        # guards that before dispatch), but a second, distinct event for
        # the same intent should still be a no-op rather than re-sending
        # the confirmation email.
        return
    brand = await brand_profiles_repository.get_by_id(conn, updated.brand_id)
    if brand is None:
        return
    user = await users_repository.get_user_by_id(conn, brand.user_id)
    if user is None:
        return
    await send_exclusivity_purchase_confirmed_email(
        user.email,
        category=updated.category,
        city=updated.city,
        starts_at=updated.starts_at.isoformat(),
        ends_at=updated.ends_at.isoformat(),
        client=resend_client,
    )
    _logger.info(
        "exclusivity_agreement_paid: agreement_id=%s brand_id=%s category=%s city=%s fee_cents=%s",
        updated.id,
        updated.brand_id,
        updated.category,
        updated.city,
        updated.fee_cents,
    )


async def _handle_payment_intent_failed(conn: asyncpg.Connection, event: "stripe.Event", settings: Settings, resend_client: ResendClient) -> None:
    """Build Prompt 10 deliverable 3: 'pending_payment' -> 'payment_failed',
    plus a notification email to the brand pointing them at
    POST /retry-payment (the only legal way out of 'payment_failed')."""
    intent = event["data"]["object"]

    if "metadata" in intent and "type" in intent["metadata"] and intent["metadata"]["type"] == "category_exclusivity":
        await _handle_exclusivity_payment_failed(conn, intent, resend_client)
        return

    campaign = await campaigns_repository.get_by_stripe_payment_intent_id(conn, intent["id"])
    if campaign is None:
        return
    updated = await campaigns_repository.set_payment_failed(conn, campaign.id)
    if updated is None:
        return
    brand = await brand_profiles_repository.get_by_id(conn, updated.brand_id)
    if brand is None:
        return
    user = await users_repository.get_user_by_id(conn, brand.user_id)
    if user is None:
        return
    await send_campaign_payment_failed_email(user.email, updated.title, resend_client)


async def _handle_exclusivity_payment_failed(conn: asyncpg.Connection, intent, resend_client: ResendClient) -> None:
    """Build Prompt 8C deliverable 4: payment_intent.payment_failed ->
    payment_status='failed', status='cancelled' (failed payment = no
    exclusivity), brand notification, admin-queue alert (logged --
    Section 8C: no dedicated admin-alert table exists in this codebase
    yet, so this follows the same logging-as-alert convention every
    other 'flag for admin' path in this file uses, e.g.
    _handle_transfer_failed's own docstring)."""
    agreement = await exclusivity_repository.get_by_payment_intent_id(conn, intent["id"])
    if agreement is None:
        return
    updated = await exclusivity_repository.mark_payment_failed(conn, agreement.id)
    if updated is None:
        return
    brand = await brand_profiles_repository.get_by_id(conn, updated.brand_id)
    if brand is None:
        return
    user = await users_repository.get_user_by_id(conn, brand.user_id)
    if user is None:
        return
    await send_exclusivity_purchase_failed_email(user.email, category=updated.category, client=resend_client)
    _logger.warning(
        "ADMIN ALERT exclusivity_payment_failed: agreement_id=%s brand_id=%s category=%s city=%s fee_cents=%s",
        updated.id,
        updated.brand_id,
        updated.category,
        updated.city,
        updated.fee_cents,
    )


def _transfer_payment_type(transfer: "stripe.StripeObject") -> str | None:
    """Build Prompt 8B deliverable 9 / Build Prompt 8G deliverable 6:
    distinguishes a milestone/challenge-bonus Transfer from a flat one
    by metadata.payment_type. Absent metadata.payment_type (every
    Transfer created before Prompt 8B, plus every flat-campaign Transfer
    created after it via stripe_service.create_payout_transfer, which
    never sets this key) is treated as flat -- backward compatible by
    construction. Metadata is a stripe.StripeObject, not a plain dict,
    on a real signed webhook -- `"payment_type" in metadata` / item
    access only, never `.get()` (see _handle_account_updated's own note
    above)."""
    if "metadata" not in transfer:
        return None
    metadata = transfer["metadata"]
    return metadata["payment_type"] if "payment_type" in metadata else None


async def _handle_transfer_paid(conn: asyncpg.Connection, event: "stripe.Event", settings: Settings, resend_client: ResendClient) -> None:
    transfer = event["data"]["object"]
    payment_type = _transfer_payment_type(transfer)
    if payment_type == "milestone":
        await payout_service.handle_transfer_paid_milestone(conn, transfer["id"], at=datetime.now(timezone.utc))
        return
    if payment_type == "challenge_conversion_bonus":
        # Build Prompt 8G deliverable 6: touches ONLY challenge_submissions
        # and rep_profiles.total_earnings_cents -- never campaign_reps or
        # any campaign payout row (never let a challenge bonus webhook
        # handler touch campaign payout rows or vice versa).
        await payout_service.handle_transfer_paid_challenge(conn, transfer["id"], at=datetime.now(timezone.utc))
        return
    await payout_service.handle_transfer_paid(conn, transfer["id"], at=datetime.now(timezone.utc))


async def _handle_transfer_failed(conn: asyncpg.Connection, event: "stripe.Event", settings: Settings, resend_client: ResendClient) -> None:
    """No admin queue table exists yet (Prompt 13) -- see
    payout_service.handle_transfer_failed's docstring for the interim
    'payout_status = failed' queue. Build Prompt 8B: the milestone
    branch below flags the campaign_rep_milestones row the same way,
    via campaign_rep_milestones.payout_status = 'failed'. Build Prompt
    8G: the challenge-bonus branch flags challenge_submissions the same
    way, isolated from both other branches."""
    transfer = event["data"]["object"]
    payment_type = _transfer_payment_type(transfer)
    if payment_type == "milestone":
        await payout_service.handle_transfer_failed_milestone(conn, transfer["id"])
        return
    if payment_type == "challenge_conversion_bonus":
        await payout_service.handle_transfer_failed_challenge(conn, transfer["id"])
        return
    await payout_service.handle_transfer_failed(conn, transfer["id"])


def _subscription_period_end(subscription) -> date:
    """Stripe subscriptions carry `current_period_end` as a unix
    timestamp on the subscription (or, in newer API versions, on each
    line item) -- `settings.recruiter_plan_credits_allotment`-many
    credits are granted for that billing cycle and reset again at the
    next one. Falls back to +30 days if the field is absent (fake test
    doubles that don't model it), rather than raising -- an approximate
    reset date is a smaller failure than rejecting the whole webhook."""
    period_end = subscription["current_period_end"] if "current_period_end" in subscription else None
    if period_end is not None:
        return datetime.fromtimestamp(period_end, tz=timezone.utc).date()
    return (datetime.now(timezone.utc) + timedelta(days=30)).date()


async def _handle_subscription_created(conn: asyncpg.Connection, event: "stripe.Event", settings: Settings, resend_client: ResendClient) -> None:
    """Build Prompt 11 deliverable 8: dual gate -- both admin approval
    (recruiter_profiles.verified) AND subscription creation are
    required before account_status flips to 'active'. No admin-approval
    UI/route exists yet (Prompt 13, same pre-existing gap noted in
    brands.py), so a recruiter who subscribes before being verified
    stays 'pending' here -- there is nothing yet that re-checks this
    once an admin verifies them later, flagged the same way
    app/routers/brands.py flags its own admin-approval gaps."""
    subscription = event["data"]["object"]
    customer_id = subscription["customer"] if "customer" in subscription else None
    if customer_id is None:
        return
    recruiter = await recruiter_profiles_repository.get_by_stripe_customer_id(conn, customer_id)
    if recruiter is None:
        return

    updated = await recruiter_profiles_repository.activate_subscription(
        conn,
        recruiter.id,
        stripe_subscription_id=subscription["id"],
        credits_allotment=settings.recruiter_plan_credits_allotment,
        credits_reset_date=_subscription_period_end(subscription),
    )
    if updated is not None and updated.verified:
        await users_repository.set_account_status(conn, updated.user_id, "active")


async def _handle_subscription_updated(conn: asyncpg.Connection, event: "stripe.Event", settings: Settings, resend_client: ResendClient) -> None:
    """Build Prompt 11 deliverable 8 ('renewed' in Section 8's prose;
    Stripe's actual event name for a renewed billing cycle is
    customer.subscription.updated). Credits do NOT roll over -- reset to
    the plan's full allotment, unused credits lost (explicit MVP
    decision). Idempotent: a duplicated delivery of the same event id
    never reaches here twice (stripe_events_repository.record_if_new
    short-circuits it before dispatch), so this always resets exactly
    once per real renewal."""
    subscription = event["data"]["object"]
    customer_id = subscription["customer"] if "customer" in subscription else None
    if customer_id is None:
        return
    recruiter = await recruiter_profiles_repository.get_by_stripe_customer_id(conn, customer_id)
    if recruiter is None:
        return
    await recruiter_profiles_repository.reset_credits(
        conn,
        recruiter.id,
        credits_allotment=settings.recruiter_plan_credits_allotment,
        credits_reset_date=_subscription_period_end(subscription),
    )


async def _handle_subscription_deleted(conn: asyncpg.Connection, event: "stripe.Event", settings: Settings, resend_client: ResendClient) -> None:
    """Build Prompt 11 deliverable 8: account moves out of 'active';
    saved profiles and message history are retained (no delete here),
    and credit-spending endpoints reject via
    recruiters.py's _require_subscription_active once
    stripe_subscription_id is cleared."""
    subscription = event["data"]["object"]
    customer_id = subscription["customer"] if "customer" in subscription else None
    if customer_id is None:
        return
    recruiter = await recruiter_profiles_repository.get_by_stripe_customer_id(conn, customer_id)
    if recruiter is None:
        return
    await recruiter_profiles_repository.clear_subscription(conn, recruiter.id)
    await users_repository.set_account_status(conn, recruiter.user_id, "pending")


_HANDLERS: dict[str, Handler] = {
    "account.updated": _handle_account_updated,
    "payment_intent.succeeded": _handle_payment_intent_succeeded,
    "payment_intent.payment_failed": _handle_payment_intent_failed,
    "transfer.paid": _handle_transfer_paid,
    "transfer.failed": _handle_transfer_failed,
    "customer.subscription.created": _handle_subscription_created,
    "customer.subscription.updated": _handle_subscription_updated,
    "customer.subscription.deleted": _handle_subscription_deleted,
}


@router.post("/webhooks/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(resend_client_dependency),
) -> dict:
    if stripe_signature is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "missing_signature", "message": "Stripe-Signature header is required."},
        )

    payload = await request.body()
    try:
        event = stripe_service.verify_webhook_signature(settings, payload=payload, signature_header=stripe_signature)
    except stripe.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_signature", "message": "Webhook signature verification failed."},
        ) from exc

    is_new = await stripe_events_repository.record_if_new(conn, event_id=event["id"], event_type=event["type"])
    if not is_new:
        # Already processed this exact event id -- Stripe retried a
        # delivery we already handled. Return 200 without re-dispatching
        # (Build Prompt 10 acceptance criterion: no duplicate side
        # effects on a repeated payload).
        return {"received": True}

    handler = _HANDLERS.get(event["type"])
    if handler is not None:
        await handler(conn, event, settings, resend_client)

    return {"received": True}
