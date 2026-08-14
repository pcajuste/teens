"""Unit tests for app/core/profile_score.py's three functions (D1
decision, teenure_athletics_playbook.md Part 0): compute_brand_completeness_score,
compute_athletic_completeness_score, compute_cross_track_score. No DB/
client fixtures needed -- pure functions."""
from __future__ import annotations

from app.core.profile_score import (
    compute_athletic_completeness_score,
    compute_brand_completeness_score,
    compute_cross_track_score,
)


def _brand(**overrides) -> int:
    kwargs = dict(
        bio=None,
        categories=[],
        school_type=None,
        instagram_handle=None,
        tiktok_handle=None,
        brand_campaigns_completed=0,
        badges_earned_count=0,
    )
    kwargs.update(overrides)
    return compute_brand_completeness_score(**kwargs)


def test_compute_brand_completeness_score_all_zero():
    assert _brand() == 0


def test_compute_brand_completeness_score_bio_only():
    assert _brand(bio="hello") == 20


def test_compute_brand_completeness_score_categories_only():
    assert _brand(categories=["gaming"]) == 20


def test_compute_brand_completeness_score_school_type_only():
    assert _brand(school_type="public") == 15


def test_compute_brand_completeness_score_one_handle():
    assert _brand(instagram_handle="x") == 15
    assert _brand(tiktok_handle="y") == 15


def test_compute_brand_completeness_score_both_handles_bonus():
    assert _brand(instagram_handle="x", tiktok_handle="y") == 20  # 15 + 5 bonus


def test_compute_brand_completeness_score_completed_campaign():
    assert _brand(brand_campaigns_completed=1) == 25
    assert _brand(brand_campaigns_completed=5) == 25  # no extra credit for more


def test_compute_brand_completeness_score_badges_capped_at_three():
    assert _brand(badges_earned_count=1) == 5
    assert _brand(badges_earned_count=3) == 15
    assert _brand(badges_earned_count=10) == 15  # capped


def test_compute_brand_completeness_score_full_score_clamped_to_100():
    score = _brand(
        bio="hello",
        categories=["gaming"],
        school_type="public",
        instagram_handle="x",
        tiktok_handle="y",
        brand_campaigns_completed=3,
        badges_earned_count=10,
    )
    assert score == 100


def _athletic(**overrides) -> int:
    kwargs = dict(
        has_sport_profile=False,
        has_gpa=False,
        has_attested_season=False,
        has_film_url=False,
        nil_acknowledged=False,
    )
    kwargs.update(overrides)
    return compute_athletic_completeness_score(**kwargs)


def test_compute_athletic_completeness_score_all_zero():
    assert _athletic() == 0


def test_compute_athletic_completeness_score_sport_profile():
    assert _athletic(has_sport_profile=True) == 30


def test_compute_athletic_completeness_score_gpa():
    assert _athletic(has_gpa=True) == 20


def test_compute_athletic_completeness_score_attested_season():
    assert _athletic(has_attested_season=True) == 20


def test_compute_athletic_completeness_score_film_url():
    assert _athletic(has_film_url=True) == 15


def test_compute_athletic_completeness_score_nil_acknowledged():
    assert _athletic(nil_acknowledged=True) == 15


def test_compute_athletic_completeness_score_all_true_sums_to_100():
    score = _athletic(
        has_sport_profile=True,
        has_gpa=True,
        has_attested_season=True,
        has_film_url=True,
        nil_acknowledged=True,
    )
    assert score == 100


def test_compute_cross_track_score_brand_only_enabled():
    score = compute_cross_track_score(
        brand_completeness_score=40, athletic_completeness_score=90, enabled_tracks=["brand"]
    )
    # athletics not enabled -- athletic score is ignored even though higher
    assert score == 40


def test_compute_cross_track_score_athletics_only_enabled():
    score = compute_cross_track_score(
        brand_completeness_score=0, athletic_completeness_score=65, enabled_tracks=["athletics"]
    )
    assert score == 65


def test_compute_cross_track_score_both_enabled_takes_greatest():
    score = compute_cross_track_score(
        brand_completeness_score=40, athletic_completeness_score=90, enabled_tracks=["brand", "athletics"]
    )
    assert score == 90

    score2 = compute_cross_track_score(
        brand_completeness_score=90, athletic_completeness_score=40, enabled_tracks=["brand", "athletics"]
    )
    assert score2 == 90
