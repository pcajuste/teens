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
