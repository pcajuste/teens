"""Server-side profile-completeness scoring (Build Prompt 5 deliverable
10). Recomputed on every PUT /reps/me -- never trusted from the client,
never partially updated by any other write path.

Scoring rule (0-100, weights sum to 100 -- picked here since neither
Teenure_MVP_Gameplan.md nor Teenure_Build_Prompts.md pins exact
weights, only "define the scoring rule explicitly in code comments"):

  - bio present (non-empty after stripping whitespace):       20 pts
  - at least one self-selected category:                      20 pts
  - school_type provided (optional at onboarding per Section 7): 15 pts
  - at least one social handle (instagram or tiktok):          15 pts
  - both social handles present:                                5 pts (on top of the 15 above)
  - at least one completed campaign (total_campaigns_completed > 0): 25 pts

Rationale for the weighting: display_name/school_name/city/state/
graduation_year are all NOT NULL at the DB layer (Section 7), so every
rep profile that exists at all already has them -- scoring them would
make the floor 100 minus a fixed constant rather than a meaningful
completeness signal. The score instead rewards the genuinely optional
fields plus the strongest completeness signal available at Phase 1: a
track record of at least one finished campaign.
"""
from __future__ import annotations

_BIO_WEIGHT = 20
_CATEGORY_WEIGHT = 20
_SCHOOL_TYPE_WEIGHT = 15
_ONE_HANDLE_WEIGHT = 15
_BOTH_HANDLES_BONUS = 5
_COMPLETED_CAMPAIGN_WEIGHT = 25

MAX_SCORE = (
    _BIO_WEIGHT
    + _CATEGORY_WEIGHT
    + _SCHOOL_TYPE_WEIGHT
    + _ONE_HANDLE_WEIGHT
    + _BOTH_HANDLES_BONUS
    + _COMPLETED_CAMPAIGN_WEIGHT
)
assert MAX_SCORE == 100


def compute_profile_completeness_score(
    *,
    bio: str | None,
    categories: list[str],
    school_type: str | None,
    instagram_handle: str | None,
    tiktok_handle: str | None,
    total_campaigns_completed: int,
) -> int:
    score = 0

    if bio and bio.strip():
        score += _BIO_WEIGHT

    if categories:
        score += _CATEGORY_WEIGHT

    if school_type:
        score += _SCHOOL_TYPE_WEIGHT

    has_instagram = bool(instagram_handle and instagram_handle.strip())
    has_tiktok = bool(tiktok_handle and tiktok_handle.strip())
    if has_instagram or has_tiktok:
        score += _ONE_HANDLE_WEIGHT
    if has_instagram and has_tiktok:
        score += _BOTH_HANDLES_BONUS

    if total_campaigns_completed > 0:
        score += _COMPLETED_CAMPAIGN_WEIGHT

    return min(score, MAX_SCORE)
