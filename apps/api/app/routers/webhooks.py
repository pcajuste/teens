"""Stripe webhook handler (Build Prompt 7 deliverable 5). Single
endpoint, dispatch table keyed by event type, per Section 8:

    payment_intent.succeeded          -> activate campaign        (Prompt 10)
    payment_intent.payment_failed     -> notify brand, revert campaign (Prompt 10)
    transfer.paid                     -> update payout_status 'paid' (Prompt 10)
    transfer.failed                   -> alert admin, flag for review (Prompt 10)
    customer.subscription.created     -> activate recruiter account (Prompt 11)
    customer.subscription.renewed     -> reset contact credits     (Prompt 11)
    customer.subscription.deleted     -> downgrade recruiter account (Prompt 11)

Only account.updated (Connect onboarding completion) is implemented in
this prompt; every other entry is a registered no-op stub so an event
Stripe sends before its owning prompt lands returns 200 (telling Stripe
not to retry) instead of 404/500. Signature verification happens before
any dispatch, and a bad signature never reaches business logic
(Section 8 acceptance criterion) -- see stripe_service.verify_webhook_signature.
"""
from __future__ import annotations

from typing import Awaitable, Callable

import asyncpg
import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.db.pool import get_connection
from app.repositories import rep_profiles_repository
from app.services import stripe_service

router = APIRouter(tags=["webhooks"])

Handler = Callable[[asyncpg.Connection, "stripe.Event"], Awaitable[None]]


async def _handle_account_updated(conn: asyncpg.Connection, event: "stripe.Event") -> None:
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


async def _noop(conn: asyncpg.Connection, event: "stripe.Event") -> None:
    return None


_HANDLERS: dict[str, Handler] = {
    "account.updated": _handle_account_updated,
    "payment_intent.succeeded": _noop,
    "payment_intent.payment_failed": _noop,
    "transfer.paid": _noop,
    "transfer.failed": _noop,
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

    handler = _HANDLERS.get(event["type"])
    if handler is not None:
        await handler(conn, event)

    return {"received": True}
