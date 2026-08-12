"""Stripe integration (Connect onboarding + platform billing).

Bodies implemented in Prompt 7 (Stripe Foundation) and Prompt 10
(Campaign Lifecycle & Payout Engine). Signatures fixed now so other
Prompt 3+ scaffolding (routers, tests) can depend on stable imports.
"""

from __future__ import annotations


def create_customer(*, user_id: str, email: str) -> str:
    """Create a Stripe Customer for a brand and return its Stripe customer ID."""
    raise NotImplementedError


def create_payment_intent(*, amount_cents: int, currency: str, customer_id: str) -> dict:
    """Create a PaymentIntent for a brand campaign budget charge.

    Returns the raw Stripe PaymentIntent object (dict-like). Amount must
    already be computed server-side — never trust a client-submitted
    amount per CLAUDE.md's financial-calculation constraint.
    """
    raise NotImplementedError


def create_connected_account(*, user_id: str, email: str) -> str:
    """Create a Stripe Connect Express account for a rep and return its account ID."""
    raise NotImplementedError


def create_transfer(*, amount_cents: int, destination_account_id: str, metadata: dict) -> dict:
    """Transfer a rep's payout share to their Connect account.

    amount_cents must already be net of the platform fee — see
    payout_service.calculate_platform_fee.
    """
    raise NotImplementedError
