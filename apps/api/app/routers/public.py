"""Unauthenticated public routes (Build Prompt 5 deliverable 12: Living
Achievement Link). No require_role dependency anywhere in this module --
that's the point. GET /verified/:token must be openable by a college
admissions officer who has never created a Teenure account.
"""
from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends

from app.db.pool import get_connection
from app.repositories import talent_profiles_repository
from app.schemas.recruiters import RecruiterSearchCardResponse
from app.schemas.talents import PublicVerifiedProfileResponse

router = APIRouter(tags=["public"])


@router.get("/verified/{token}", response_model=PublicVerifiedProfileResponse)
async def get_verified_profile(
    token: str,
    conn: asyncpg.Connection = Depends(get_connection),
) -> PublicVerifiedProfileResponse:
    """Returns public=False (not a 404) when the token exists but the
    talent has verified_profile_public turned off -- spec: the talent
    may share the link before flipping visibility on and the recipient
    should see an explanatory state, not a generic "not found". A
    genuinely unknown/invalid token still 200s with public=False and no
    other fields set, rather than 404ing -- this avoids using response
    status codes to let a caller enumerate which tokens exist."""
    profile = await talent_profiles_repository.get_public_profile_by_token(conn, token)
    if profile is None or not profile.verified_profile_public:
        return PublicVerifiedProfileResponse(public=False)
    return PublicVerifiedProfileResponse(
        public=True,
        display_name=profile.display_name,
        school_name=profile.school_name,
        graduation_year=profile.graduation_year,
        city=profile.city,
        categories=profile.categories,
        badges=profile.badges,
        total_campaigns_completed=profile.total_campaigns_completed,
        average_rating=profile.average_rating,
        total_earnings_cents=profile.total_earnings_cents,
        last_updated=profile.updated_at,
    )


@router.get("/demo/recruiter-search", response_model=list[RecruiterSearchCardResponse])
async def demo_recruiter_search(
    graduation_year: int | None = None,
    city: str | None = None,
    state: str | None = None,
    categories: str | None = None,
    min_campaigns: int | None = None,
    min_rating: float | None = None,
    limit: int = 20,
    offset: int = 0,
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[RecruiterSearchCardResponse]:
    """Build Prompt 12A part 1: the recruiter-preview demo page's live
    search, unauthenticated and free. Deliberately calls the exact same
    repository query as GET /recruiters/talents/search (Build Prompt
    11) so results are provably the same no-PII card shape a signed-in
    recruiter would see -- no parallel fake search implementation, no
    credit deduction, no recruiter row required."""
    category_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None

    cards = await talent_profiles_repository.search_for_recruiter(
        conn,
        graduation_year=graduation_year,
        city=city,
        state=state,
        categories=category_list,
        min_campaigns=min_campaigns,
        min_rating=min_rating,
        limit=limit,
        offset=offset,
    )
    return [
        RecruiterSearchCardResponse(
            talent_id=c.talent_id,
            city=c.city,
            state=c.state,
            graduation_year=c.graduation_year,
            school_type=c.school_type,
            categories=c.categories,
            profile_completeness_score=c.profile_completeness_score,
            average_rating=c.average_rating,
            total_campaigns_completed=c.total_campaigns_completed,
            challenges_converted_count=c.challenges_converted_count,
            challenge_conversion_rate=c.challenge_conversion_rate,
            badge_count=c.badge_count,
            badge_titles=c.badge_titles or [],
        )
        for c in cards
    ]
