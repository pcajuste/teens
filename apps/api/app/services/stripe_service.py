"""Stripe integration shell.

Connect onboarding wires up in Prompt 7 (Stripe Foundation); campaign
checkout/charges and rep payouts wire up in Prompt 10 (Campaign
Lifecycle & Payout Engine). All amounts are server-computed cents —
never accept a client-submitted amount (Section 9).
"""
from __future__ import annotations


async def create_connect_account(user_id: str) -> str:
    """Create a Stripe Connect Express account for a rep and return its
    account id. Prompt 7."""
    raise NotImplementedError


async def create_connect_onboarding_link(stripe_account_id: str, return_url: str) -> str:
    """Return a hosted onboarding link URL for the given Connect account.
    Prompt 7."""
    raise NotImplementedError


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


async def verify_webhook_signature(payload: bytes, signature_header: str) -> dict:
    """Verify a Stripe webhook payload against STRIPE_WEBHOOK_SECRET and
    return the parsed event. Prompt 7/10/11 (subscription events)."""
    raise NotImplementedError
