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


async def create_payment_intent(
    settings: Settings, *, amount_cents: int, metadata: dict, customer_id: str | None = None
) -> tuple[str, str]:
    """Build Prompt 8 deliverable 4 (POST /brands/campaigns/:id/activate
    "kicks off PaymentIntent"), `customer_id` wired in by Prompt 10
    deliverable 2 ("against brand's stripe_customer_id"). Returns
    (payment_intent_id, client_secret) -- the id is what
    campaigns.stripe_payment_intent_id stores, the client_secret is what
    the Prompt 9 frontend needs to collect card details via Stripe
    Elements. No payment method is attached here; the PaymentIntent
    starts in 'requires_payment_method'. `amount_cents` is always
    budget_cents, computed server-side at campaign creation
    (app/services/campaign_service.py) -- never a client-submitted
    amount (Section 9). `customer_id` is optional because Prompt 8's
    brand.stripe_customer_id is only ever populated lazily by the
    caller (app/routers/brands.py's activate_campaign creates the
    Customer on first activation, same create-or-reuse shape as
    create_connect_account/create_connect_onboarding_link) -- passing
    None omits the `customer` param entirely rather than sending an
    empty string Stripe would reject.

    Distinct from create_campaign_checkout_session below: that's the
    alternative Checkout-Session-based integration Prompt 9's own text
    says is still an open choice ("Elements or Checkout -- pick one").
    This function is the primitive either choice can use; a PaymentIntent
    id is what the campaigns schema (Section 7) actually stores."""
    _configure(settings)
    kwargs = {"amount": amount_cents, "currency": "usd", "metadata": metadata}
    if customer_id is not None:
        kwargs["customer"] = customer_id
    intent = await asyncio.to_thread(stripe.PaymentIntent.create, **kwargs)
    return intent.id, intent.client_secret


async def create_campaign_checkout_session(campaign_id: str, amount_cents: int) -> str:
    """Create a Checkout Session for a brand funding a campaign; amount
    is computed server-side from the campaign budget, never from the
    client. Prompt 10."""
    raise NotImplementedError


async def create_payout_transfer(
    settings: Settings, *, stripe_account_id: str, amount_cents: int, campaign_rep_id: str
) -> str:
    """Transfer a rep's earned share (campaign_reps.payout_cents,
    already fixed at campaign-creation time -- see
    app/services/payout_service.py's module docstring) to their Connect
    account. Called only after app/services/payout_service.release_payout
    has confirmed the row is 'confirmed', payout_cents is set, and the
    rep's Connect onboarding is complete. `campaign_rep_id` is recorded
    in metadata so a Transfer is traceable back to the row from the
    Stripe dashboard, mirroring create_connect_account's metadata
    convention. Returns the Transfer id, stored on
    campaign_reps.stripe_transfer_id."""
    _configure(settings)
    transfer = await asyncio.to_thread(
        stripe.Transfer.create,
        amount=amount_cents,
        currency="usd",
        destination=stripe_account_id,
        metadata={"campaign_rep_id": campaign_rep_id},
    )
    return transfer.id


async def refund_campaign(
    settings: Settings, *, payment_intent_id: str, amount_cents: int, campaign_id: str
) -> str:
    """Issue a partial refund against the campaign's captured
    PaymentIntent. See app/routers/brands.py's cancel_campaign for the
    amount computation (un-paid remainder of budget_cents, per Prompt
    10's own deliverable text) and docs/campaign-cancellation-refund-policy.md
    for why that's the interim decision rather than a full refund.
    `amount_cents` of 0 is never passed here -- the caller skips this
    call entirely in that case, since Stripe rejects a zero-amount
    refund."""
    _configure(settings)
    refund = await asyncio.to_thread(
        stripe.Refund.create,
        payment_intent=payment_intent_id,
        amount=amount_cents,
        metadata={"campaign_id": campaign_id},
    )
    return refund.id


async def get_payment_intent_receipt_url(settings: Settings, *, payment_intent_id: str) -> str | None:
    """Build Prompt 8 deliverable 10: "Billing history: Stripe-hosted
    receipt URLs, not reimplemented invoices." No local storage of
    receipts at all -- this is a live passthrough to Stripe's own
    PaymentIntent -> latest_charge -> receipt_url, which only exists
    once a charge has actually succeeded (Prompt 10 territory; before
    that this returns None, which is the correct/honest answer for a
    'draft'/'pending_payment' campaign, not an error)."""
    _configure(settings)
    intent = await asyncio.to_thread(
        stripe.PaymentIntent.retrieve, payment_intent_id, expand=["latest_charge"]
    )
    charge = intent["latest_charge"] if "latest_charge" in intent else None
    if charge is None or isinstance(charge, str):
        return None
    return charge["receipt_url"] if "receipt_url" in charge else None


async def create_credit_topup_payment_intent(
    settings: Settings, *, amount_cents: int, credits: int, recruiter_id: str, customer_id: str | None = None
) -> tuple[str, str]:
    """Build Prompt 11 deliverable 7 ("Credit top-up: Stripe one-time
    charge, increments credits on webhook, idempotent"). Thin wrapper
    over create_payment_intent that tags the intent's metadata with
    type='recruiter_credit_topup' so app/routers/webhooks.py's
    payment_intent.succeeded handler can distinguish a credit purchase
    from a brand campaign charge without a second webhook endpoint."""
    return await create_payment_intent(
        settings,
        amount_cents=amount_cents,
        metadata={"type": "recruiter_credit_topup", "recruiter_id": recruiter_id, "credits": str(credits)},
        customer_id=customer_id,
    )


def verify_webhook_signature(settings: Settings, *, payload: bytes, signature_header: str) -> stripe.Event:
    """Verify a Stripe webhook payload against STRIPE_WEBHOOK_SECRET and
    return the parsed event. Raises stripe.error.SignatureVerificationError
    on an invalid/forged signature -- callers must let that propagate
    into a rejected request, never swallow it (Section 8 acceptance
    criterion: invalid webhook signature rejected before any business
    logic runs). Synchronous: this does local HMAC verification only,
    no network call, so there's nothing to offload to a thread."""
    return stripe.Webhook.construct_event(payload, signature_header, settings.stripe_webhook_secret)
