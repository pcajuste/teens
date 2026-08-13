"""Campaign-creation-time computations (Build Prompt 8 deliverable 3).

Distinct from app/services/payout_service.py's calculate_platform_fee_split
stub, which is Prompt 10's concern (the per-talent transfer amount at
payout time) -- this module computes the one-time budget_cents split
that happens when a brand creates a campaign, before any talent is even
invited. Kept in its own module rather than un-stubbing payout_service.py
so this prompt doesn't reach into a later prompt's file.

All money math is integer cents throughout -- never float (Section 9:
server-computed only, and float cents risk silent rounding drift)."""
from __future__ import annotations


async def get_or_create_stripe_customer_id(conn, settings, brand: "brand_profiles_repository.BrandProfile") -> str:
    """Lazy create-or-reuse, same shape as
    stripe_service.create_connect_account/create_connect_onboarding_link's
    create-or-resume pattern -- Build Prompt 8's own build-log
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


def compute_campaign_fee_split(*, budget_cents: int, max_talents: int, platform_fee_percent: int) -> tuple[int, int, int]:
    """Returns (platform_fee_cents, talent_pool_cents, payout_per_talent_cents).

    platform_fee_cents is round-half-up of budget_cents * platform_fee_percent / 100,
    computed entirely in integer arithmetic ((budget_cents * percent + 50) // 100)
    to avoid float imprecision. talent_pool_cents is the exact remainder
    (budget_cents - platform_fee_cents), which guarantees
    talent_pool_cents + platform_fee_cents == budget_cents always, by
    construction rather than by rounding both independently and hoping
    they add up.

    payout_per_talent_cents is talent_pool_cents // max_talents (integer floor
    division) -- a flat per-talent rate, matching the single
    payout_per_talent_cents column on campaigns (Section 7). Any remainder
    from that division (talent_pool_cents % max_talents) is not distributed to
    any talent; it's an intentional simplification, not a bug -- splitting
    a few leftover cents across talents unevenly would need a `remainder
    goes to whom` rule nobody has specified.
    """
    if budget_cents < 0:
        raise ValueError("budget_cents must be >= 0")
    if max_talents <= 0:
        raise ValueError("max_talents must be > 0")

    platform_fee_cents = (budget_cents * platform_fee_percent + 50) // 100
    talent_pool_cents = budget_cents - platform_fee_cents
    payout_per_talent_cents = talent_pool_cents // max_talents
    return platform_fee_cents, talent_pool_cents, payout_per_talent_cents


class MilestoneValidationError(ValueError):
    """Raised by validate_milestones below; the router catches this and
    turns it into a 400 with `str(exc)` as the message (Build Prompt 8B:
    "reject if the brand submits percentages that sum to 99 or 101 --
    do not silently adjust; return a clear validation error")."""


_MIN_MILESTONES = 2
_MAX_MILESTONES = 5


def validate_milestones(milestones: list[dict]) -> None:
    """Server-side validation for POST /brands/campaigns when
    payment_type='milestone' (Build Prompt 8B deliverable 1). Every
    rule below is drawn directly from the prompt's own bullet list --
    raises MilestoneValidationError with a specific message on the
    first rule violated, never silently coerces/adjusts the brand's
    input.

    `milestones` is the already-pydantic-validated list of dicts (each
    with milestone_number/title/description/verification_method/
    payout_percentage/sequence_required) -- field-level shape (e.g.
    payout_percentage being an int) is enforced by the pydantic schema
    before this ever runs; this function only checks the cross-field/
    cross-milestone business rules pydantic's per-field validators
    can't express."""
    if not (_MIN_MILESTONES <= len(milestones) <= _MAX_MILESTONES):
        raise MilestoneValidationError(
            f"milestone campaigns require between {_MIN_MILESTONES} and {_MAX_MILESTONES} milestones, got {len(milestones)}"
        )

    numbers = [m["milestone_number"] for m in milestones]
    if numbers != list(range(1, len(milestones) + 1)):
        raise MilestoneValidationError("milestone_number values must be sequential starting from 1")

    total_percentage = sum(m["payout_percentage"] for m in milestones)
    if total_percentage != 100:
        raise MilestoneValidationError(
            f"milestone payout_percentage values must sum to exactly 100, got {total_percentage}"
        )

    ordered = sorted(milestones, key=lambda m: m["milestone_number"])
    if not any(m["sequence_required"] for m in ordered):
        raise MilestoneValidationError("at least one milestone must have sequence_required = true")

    # "milestones with sequence_required = false may only appear after
    # all sequence_required milestones (i.e., non-sequential milestones
    # are always the final milestone(s) in a campaign)": once we've
    # seen a non-sequential milestone, every milestone after it (in
    # milestone_number order) must also be non-sequential.
    seen_non_sequential = False
    for m in ordered:
        if not m["sequence_required"]:
            seen_non_sequential = True
        elif seen_non_sequential:
            raise MilestoneValidationError(
                "sequence_required milestones must all come before any non-sequential milestone"
            )
