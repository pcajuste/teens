"""Payout and fee-split calculation shell. Prompt 10.

All financial math happens here, server-side only (Section 9) — never
trust a client-submitted amount, and never duplicate this math in
apps/web.
"""
from __future__ import annotations


def calculate_platform_fee_split(amount_cents: int, platform_fee_percent: int) -> tuple[int, int]:
    """Return (platform_cut_cents, rep_payout_cents) for a given gross
    campaign amount."""
    raise NotImplementedError


async def initiate_payout(campaign_rep_id: str) -> str:
    """Mark a campaign_reps deliverable as confirmed, compute the rep's
    share, and initiate the Stripe transfer. Returns payout_status."""
    raise NotImplementedError


async def handle_transfer_failed(stripe_transfer_id: str) -> None:
    """React to a Stripe transfer.failed webhook: mark payout_status
    'failed' and surface it in the admin queue (Prompt 13)."""
    raise NotImplementedError
