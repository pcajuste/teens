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


async def get_or_create_stripe_customer_id(conn, settings, brand: "brand_profiles_repository.BrandProfile") -> str:
    """Lazy create-or-reuse, same shape as
    stripe_service.create_connect_account/create_connect_onboarding_link's
    create-or-resume pattern for reps. Build Prompt 8's own build-log
    note left this unwired ("service function ready for admin approval
    flow, Prompt 13") since nothing called stripe_service.create_customer
    yet; Prompt 10 deliverable 2 ("Wire /activate to create Stripe
    PaymentIntent... against brand's stripe_customer_id") needs one to
    exist, and waiting on Prompt 13's admin-approval flow isn't a
    prerequisite for that -- a brand's Stripe Customer identity doesn't
    depend on admin verification, so this creates it on first activation
    instead."""
    from app.repositories import brand_profiles_repository
    from app.repositories import users_repository
    from app.services import stripe_service

    if brand.stripe_customer_id:
        return brand.stripe_customer_id
    user = await users_repository.get_user_by_id(conn, brand.user_id)
    customer_id = await stripe_service.create_customer(
        settings, email=user.email, metadata={"role": "brand", "brand_id": brand.id}
    )
    await brand_profiles_repository.set_stripe_customer_id(conn, brand.id, customer_id)
    return customer_id


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
