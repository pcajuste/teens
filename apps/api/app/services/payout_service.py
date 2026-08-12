"""Server-side financial calculations for campaign payouts.

Bodies implemented in Prompt 10 (Campaign Lifecycle & Payout Engine).
All amounts are integer cents; per CLAUDE.md, these calculations must
only ever run server-side, never trusting a client-submitted amount.
"""

from __future__ import annotations


def calculate_platform_fee(*, gross_amount_cents: int, fee_percent: int) -> dict:
    """Split a gross campaign amount into {platform_fee_cents, rep_net_cents}.

    fee_percent comes from settings.stripe_platform_fee_percent
    (Section 4: platform takes 30-40% of campaign budget), not a
    client-supplied value.
    """
    raise NotImplementedError


def release_payout(*, campaign_rep_id: str) -> dict:
    """Release a confirmed campaign_reps row's payout via stripe_service.create_transfer.

    Also responsible for triggering rep_profiles cached-field recompute
    (see docs/rep-cached-fields-sync.md) after a successful transfer.
    """
    raise NotImplementedError
