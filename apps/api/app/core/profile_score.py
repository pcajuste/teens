"""Server-side profile-completeness scoring.

Three functions, not one (D1 decision, teenure_athletics_playbook.md
Part 0):
  - compute_brand_completeness_score: brand track, 0-100 (renamed from
    the original single-track compute_profile_completeness_score --
    same weights, same logic, only the total_campaigns_completed param
    is renamed to brand_campaigns_completed to match the Migration A
    column rename)
  - compute_athletic_completeness_score: athletic track, 0-100
  - compute_cross_track_score: GREATEST of active track scores --
    stored as profile_completeness_score, used for recruiter search
    ordering

Industry reference: LinkedIn's All-Star strength model. Section scores
are independent; overall strength = highest section, not penalized by
unset optional sections.
"""
from __future__ import annotations

# ── Brand track weights (unchanged from v1, only renamed) ──────────────
_BRAND_BIO_WEIGHT = 20
_BRAND_CATEGORY_WEIGHT = 20
_BRAND_SCHOOL_TYPE_WEIGHT = 15
_BRAND_ONE_HANDLE_WEIGHT = 15
_BRAND_BOTH_HANDLES_BONUS = 5
_BRAND_COMPLETED_CAMPAIGN_WEIGHT = 25
_BRAND_BADGE_WEIGHT = 5
_BRAND_MAX_BADGES_COUNTED = 3

_BRAND_MAX_SCORE = (
    _BRAND_BIO_WEIGHT
    + _BRAND_CATEGORY_WEIGHT
    + _BRAND_SCHOOL_TYPE_WEIGHT
    + _BRAND_ONE_HANDLE_WEIGHT
    + _BRAND_BOTH_HANDLES_BONUS
    + _BRAND_COMPLETED_CAMPAIGN_WEIGHT
)
assert _BRAND_MAX_SCORE == 100

# ── Athletic track weights (D1 decision, D3/NAIA coach research) ───────
_ATHLETIC_SPORT_PROFILE_WEIGHT = 30   # has sport + positions
_ATHLETIC_GPA_WEIGHT = 20             # GPA provided
_ATHLETIC_SEASON_WEIGHT = 20          # at least one attested season
_ATHLETIC_FILM_WEIGHT = 15            # Hudl or MaxPreps URL
_ATHLETIC_NIL_WEIGHT = 15             # NIL rules acknowledged for state


def compute_brand_completeness_score(
    *,
    bio: str | None,
    categories: list[str],
    school_type: str | None,
    instagram_handle: str | None,
    tiktok_handle: str | None,
    brand_campaigns_completed: int,
    badges_earned_count: int = 0,
) -> int:
    score = 0
    if bio and bio.strip():
        score += _BRAND_BIO_WEIGHT
    if categories:
        score += _BRAND_CATEGORY_WEIGHT
    if school_type:
        score += _BRAND_SCHOOL_TYPE_WEIGHT
    has_instagram = bool(instagram_handle and instagram_handle.strip())
    has_tiktok = bool(tiktok_handle and tiktok_handle.strip())
    if has_instagram or has_tiktok:
        score += _BRAND_ONE_HANDLE_WEIGHT
    if has_instagram and has_tiktok:
        score += _BRAND_BOTH_HANDLES_BONUS
    if brand_campaigns_completed > 0:
        score += _BRAND_COMPLETED_CAMPAIGN_WEIGHT
    score += min(max(badges_earned_count, 0), _BRAND_MAX_BADGES_COUNTED) * _BRAND_BADGE_WEIGHT
    return min(score, 100)


def compute_athletic_completeness_score(
    *,
    has_sport_profile: bool,
    has_gpa: bool,
    has_attested_season: bool,
    has_film_url: bool,
    nil_acknowledged: bool,
) -> int:
    """D1 decision weights. Called from:
    - athletics_router on any sport_profile upsert
    - talent_profiles_repository.recompute_athletic_cached_totals after attestation
    - Recomputed in the same positions brand_completeness_score is recomputed."""
    score = 0
    if has_sport_profile:
        score += _ATHLETIC_SPORT_PROFILE_WEIGHT
    if has_gpa:
        score += _ATHLETIC_GPA_WEIGHT
    if has_attested_season:
        score += _ATHLETIC_SEASON_WEIGHT
    if has_film_url:
        score += _ATHLETIC_FILM_WEIGHT
    if nil_acknowledged:
        score += _ATHLETIC_NIL_WEIGHT
    return min(score, 100)


def compute_cross_track_score(
    brand_completeness_score: int,
    athletic_completeness_score: int,
    enabled_tracks: list[str],
) -> int:
    """GREATEST of active track scores -- stored as profile_completeness_score.
    A talent on brand-only with 0% athletic score still gets their full
    brand score here. A brand=40%, athletic=90% talent gets 90.
    Industry reference: LinkedIn All-Star = highest section strength."""
    scores = [brand_completeness_score]
    if "athletics" in enabled_tracks:
        scores.append(athletic_completeness_score)
    return max(scores)
