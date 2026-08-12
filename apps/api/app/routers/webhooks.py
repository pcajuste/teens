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

from datetime import datetime, timezone
from typing import Awaitable, Callable

import asyncpg
import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.db.pool import get_connection
from app.repositories import brand_profiles_repository, campaigns_repository, rep_profiles_repository, stripe_events_repository, users_repository
from app.services import payout_service, stripe_service
from app.services.email_service import send_campaign_payment_failed_email
from app.services.resend_client import ResendClient, resend_client_dependency

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
    replayed event after cancellation) is a silent no-op."""
    intent = event["data"]["object"]
    campaign = await campaigns_repository.get_by_stripe_payment_intent_id(conn, intent["id"])
    if campaign is None:
        return
    await campaigns_repository.set_active(conn, campaign.id)


async def _handle_payment_intent_failed(conn: asyncpg.Connection, event: "stripe.Event", settings: Settings, resend_client: ResendClient) -> None:
    """Build Prompt 10 deliverable 3: 'pending_payment' -> 'payment_failed',
    plus a notification email to the brand pointing them at
    POST /retry-payment (the only legal way out of 'payment_failed')."""
    intent = event["data"]["object"]
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


async def _handle_transfer_paid(conn: asyncpg.Connection, event: "stripe.Event", settings: Settings, resend_client: ResendClient) -> None:
    transfer = event["data"]["object"]
    await payout_service.handle_transfer_paid(conn, transfer["id"], at=datetime.now(timezone.utc))


async def _handle_transfer_failed(conn: asyncpg.Connection, event: "stripe.Event", settings: Settings, resend_client: ResendClient) -> None:
    """No admin queue table exists yet (Prompt 13) -- see
    payout_service.handle_transfer_failed's docstring for the interim
    'payout_status = failed' queue."""
    transfer = event["data"]["object"]
    await payout_service.handle_transfer_failed(conn, transfer["id"])


async def _noop(conn: asyncpg.Connection, event: "stripe.Event", settings: Settings, resend_client: ResendClient) -> None:
    return None


_HANDLERS: dict[str, Handler] = {
    "account.updated": _handle_account_updated,
    "payment_intent.succeeded": _handle_payment_intent_succeeded,
    "payment_intent.payment_failed": _handle_payment_intent_failed,
    "transfer.paid": _handle_transfer_paid,
    "transfer.failed": _handle_transfer_failed,
    "customer.subscription.created": _noop,
    "customer.subscription.updated": _noop,
    "customer.subscription.deleted": _noop,
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
