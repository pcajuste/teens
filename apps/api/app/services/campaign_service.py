"""Campaign-creation-time computations (Build Prompt 8 deliverable 3).

Distinct from app/services/payout_service.py's calculate_platform_fee_split
stub, which is Prompt 10's concern (the per-rep transfer amount at
payout time) -- this module computes the one-time budget_cents split
that happens when a brand creates a campaign, before any rep is even
invited. Kept in its own module rather than un-stubbing payout_service.py
so this prompt doesn't reach into a later prompt's file.

All money math is integer cents throughout -- never float (Section 9:
server-computed only, and float cents risk silent rounding drift)."""
from __future__ import annotations


def compute_campaign_fee_split(*, budget_cents: int, max_reps: int, platform_fee_percent: int) -> tuple[int, int, int]:
    """Returns (platform_fee_cents, rep_pool_cents, payout_per_rep_cents).

    platform_fee_cents is round-half-up of budget_cents * platform_fee_percent / 100,
    computed entirely in integer arithmetic ((budget_cents * percent + 50) // 100)
    to avoid float imprecision. rep_pool_cents is the exact remainder
    (budget_cents - platform_fee_cents), which guarantees
    rep_pool_cents + platform_fee_cents == budget_cents always, by
    construction rather than by rounding both independently and hoping
    they add up.

    payout_per_rep_cents is rep_pool_cents // max_reps (integer floor
    division) -- a flat per-rep rate, matching the single
    payout_per_rep_cents column on campaigns (Section 7). Any remainder
    from that division (rep_pool_cents % max_reps) is not distributed to
    any rep; it's an intentional simplification, not a bug -- splitting
    a few leftover cents across reps unevenly would need a `remainder
    goes to whom` rule nobody has specified.
    """
    if budget_cents < 0:
        raise ValueError("budget_cents must be >= 0")
    if max_reps <= 0:
        raise ValueError("max_reps must be > 0")

    platform_fee_cents = (budget_cents * platform_fee_percent + 50) // 100
    rep_pool_cents = budget_cents - platform_fee_cents
    payout_per_rep_cents = rep_pool_cents // max_reps
    return platform_fee_cents, rep_pool_cents, payout_per_rep_cents
