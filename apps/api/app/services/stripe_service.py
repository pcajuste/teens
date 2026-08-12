"""Stripe integration: Connect onboarding and platform billing customer
creation (Build Prompt 7). Campaign checkout/charges and rep payouts
wire up in Prompt 10 (Campaign Lifecycle & Payout Engine); subscription
billing in Prompt 11. All amounts are server-computed cents -- never
accept a client-submitted amount (Section 9).

Every function takes `settings` explicitly (this module has no
import-time Stripe API key configuration) and goes through the `stripe`
module reference below rather than importing `stripe.Account` etc.
directly at call sites, so tests can swap in a fake via
`monkeypatch.setattr(stripe_service, "stripe", fake)` -- same seam
style as the rest of this codebase's monkeypatch-based test doubles
(see tests/test_security.py, tests/test_parent_portal.py), rather than
inventing a Protocol/Fake-client abstraction not used anywhere else in
this file's original stub shape.

The `stripe` Python SDK's classic resource calls (stripe.Account.create,
etc.) are synchronous (blocking network I/O) -- every call here runs
via asyncio.to_thread so it doesn't block the event loop that's serving
every other concurrent request.

Minors and Stripe Connect: see docs/stripe-minors-policy.md before
changing anything about what identity information create_connect_account
collects or how onboarding_link is generated. Short version: Stripe
Express/Custom accounts support account holders as young as 13 with an
adult "Representative" (parent/guardian) added to the account -- Stripe's
own hosted onboarding (the Account Link this module generates) surfaces
that requirement dynamically based on the individual's date of birth, so
this module does not need special-case minor-vs-adult branching. It
creates a standard Express account and hands the rep a standard
onboarding link either way.
"""
from __future__ import annotations

import asyncio

import stripe

from app.core.config import Settings


def _configure(settings: Settings) -> None:
    # Cheap and idempotent -- stripe.api_key is a plain module attribute,
    # not a client object, so setting it per-call (rather than once at
    # import time) is what allows tests to swap Settings between cases
    # without import-order tricks.
    stripe.api_key = settings.stripe_secret_key


async def create_customer(settings: Settings, *, email: str, metadata: dict) -> str:
    """Creates a Stripe Customer for platform billing -- brand campaign
    invoicing and (Prompt 11) recruiter subscription billing both use
    this; which use case is recorded via `metadata` (e.g.
    {"role": "brand", "user_id": ...}) since Stripe Customers aren't
    otherwise tagged by caller. Returns the Stripe customer id."""
    _configure(settings)
    customer = await asyncio.to_thread(stripe.Customer.create, email=email, metadata=metadata)
    return customer.id


async def create_connect_account(settings: Settings, *, email: str, metadata: dict) -> str:
    """Creates a Stripe Connect Express account for a rep and returns its
    account id. `metadata` should include {"user_id": ..., "rep_profile_id": ...}
    so the account is traceable back to a rep from the Stripe dashboard.
    Does not collect date of birth or identity details itself -- that
    happens in Stripe's hosted onboarding (create_connect_onboarding_link),
    which is also where Stripe surfaces the Representative/guardian
    requirement for a rep under 18. See docs/stripe-minors-policy.md."""
    _configure(settings)
    account = await asyncio.to_thread(
        stripe.Account.create,
        type="express",
        email=email,
        business_type="individual",
        capabilities={"transfers": {"requested": True}},
        metadata=metadata,
    )
    return account.id


async def create_connect_onboarding_link(settings: Settings, *, account_id: str, refresh_url: str, return_url: str) -> str:
    """Returns a hosted onboarding link URL for the given Connect
    account. `refresh_url` is where Stripe sends the rep back if the
    link expires mid-flow (must be capable of generating a fresh link,
    i.e. the same endpoint that issued this one); `return_url` is where
    they land after completing (or exiting) onboarding -- onboarding
    completion itself is confirmed asynchronously via the
    account.updated webhook, never assumed just because the rep reached
    return_url."""
    _configure(settings)
    link = await asyncio.to_thread(
        stripe.AccountLink.create,
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return link.url


async def create_campaign_checkout_session(campaign_id: str, amount_cents: int) -> str:
    """Create a Checkout Session for a brand funding a campaign; amount
    is computed server-side from the campaign budget, never from the
    client. Prompt 10."""
    raise NotImplementedError


async def create_payout_transfer(stripe_account_id: str, amount_cents: int, campaign_rep_id: str) -> str:
    """Transfer a rep's earned share for a completed campaign deliverable
    to their Connect account. Prompt 10."""
    raise NotImplementedError


async def refund_campaign(campaign_id: str, amount_cents: int) -> str:
    """Issue a full or partial refund per the cancellation policy defined
    in Prompt 8. Prompt 10."""
    raise NotImplementedError


def verify_webhook_signature(settings: Settings, *, payload: bytes, signature_header: str) -> stripe.Event:
    """Verify a Stripe webhook payload against STRIPE_WEBHOOK_SECRET and
    return the parsed event. Raises stripe.error.SignatureVerificationError
    on an invalid/forged signature -- callers must let that propagate
    into a rejected request, never swallow it (Section 8 acceptance
    criterion: invalid webhook signature rejected before any business
    logic runs). Synchronous: this does local HMAC verification only,
    no network call, so there's nothing to offload to a thread."""
    return stripe.Webhook.construct_event(payload, signature_header, settings.stripe_webhook_secret)
