from __future__ import annotations

import pytest

from app.services.campaign_service import compute_campaign_fee_split


@pytest.mark.parametrize(
    "budget_cents,max_talents,percent",
    [
        (100_000, 10, 35),
        (100_001, 7, 35),  # doesn't divide evenly by max_talents or percent
        (1, 1, 35),  # smallest possible budget
        (3, 1, 50),  # 1.5 cents platform fee -- exact half-cent rounding boundary
        (999_999, 13, 30),
        (10_000_000, 3, 40),
    ],
)
def test_fee_split_always_sums_to_budget(budget_cents, max_talents, percent):
    platform_fee_cents, talent_pool_cents, payout_per_talent_cents = compute_campaign_fee_split(
        budget_cents=budget_cents, max_talents=max_talents, platform_fee_percent=percent
    )
    assert platform_fee_cents + talent_pool_cents == budget_cents
    assert payout_per_talent_cents * max_talents <= talent_pool_cents


def test_half_cent_rounds_up():
    # 3 cents * 50% = 1.5 cents -- round-half-up means 2, not 1 (banker's
    # rounding, Python's default round(), would give 2 here too by
    # coincidence -- see the next case for one where they'd diverge).
    platform_fee_cents, talent_pool_cents, _ = compute_campaign_fee_split(budget_cents=3, max_talents=1, platform_fee_percent=50)
    assert platform_fee_cents == 2
    assert talent_pool_cents == 1


def test_half_cent_rounds_up_not_banker_rounding():
    # 1 cent * 50% = 0.5 cents. Banker's rounding (round-half-to-even)
    # would give 0 (nearest even). Round-half-up (what this function
    # implements, deliberately, since money should round consistently
    # rather than alternate based on parity) gives 1.
    platform_fee_cents, talent_pool_cents, _ = compute_campaign_fee_split(budget_cents=1, max_talents=1, platform_fee_percent=50)
    assert platform_fee_cents == 1
    assert talent_pool_cents == 0


def test_payout_per_talent_floors_and_does_not_overallocate():
    # talent_pool_cents=100, max_talents=3 -> 33 each, 1 cent unallocated.
    platform_fee_cents, talent_pool_cents, payout_per_talent_cents = compute_campaign_fee_split(
        budget_cents=200, max_talents=3, platform_fee_percent=50
    )
    assert talent_pool_cents == 100
    assert payout_per_talent_cents == 33
    assert payout_per_talent_cents * 3 == 99 < talent_pool_cents


def test_zero_budget_is_allowed_and_splits_to_zero():
    platform_fee_cents, talent_pool_cents, payout_per_talent_cents = compute_campaign_fee_split(
        budget_cents=0, max_talents=5, platform_fee_percent=35
    )
    assert (platform_fee_cents, talent_pool_cents, payout_per_talent_cents) == (0, 0, 0)


def test_negative_budget_rejected():
    with pytest.raises(ValueError):
        compute_campaign_fee_split(budget_cents=-1, max_talents=5, platform_fee_percent=35)


def test_zero_max_reps_rejected():
    with pytest.raises(ValueError):
        compute_campaign_fee_split(budget_cents=100, max_talents=0, platform_fee_percent=35)
