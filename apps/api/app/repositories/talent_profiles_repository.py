"""Data access for public.talent_profiles.

Follows the same shape as users_repository.py / parent_records_repository.py:
every function takes an explicit asyncpg connection, frozen/slots
dataclass with `from_row`, jsonb-free here since `categories` is a
Postgres TEXT[] (asyncpg maps it to a Python list directly, no
json.dumps/loads needed, unlike parent_records.values_filters which is
JSONB).
"""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime

import asyncpg

_COLUMNS = (
    "id, user_id, display_name, school_name, school_type, city, state, graduation_year, "
    "bio, categories, instagram_handle, tiktok_handle, recruiter_visible, "
    "brand_campaigns_completed, total_earnings_cents, brand_average_rating, "
    "profile_completeness_score, stripe_account_id, stripe_onboarding_complete, "
    "challenges_submitted_count, challenges_converted_count, badges, badges_earned_count, "
    "achievement_link_token, verified_profile_public, earnings_visible_on_public_profile, "
    "enabled_tracks, brand_completeness_score, athletic_completeness_score, "
    "athletic_seasons_completed, athletic_recruiter_interest_count, "
    "created_at, updated_at"
)


@dataclass(frozen=True, slots=True)
class TalentProfile:
    id: str
    user_id: str
    display_name: str
    school_name: str
    school_type: str | None
    city: str
    state: str
    graduation_year: int
    bio: str | None
    categories: list[str]
    instagram_handle: str | None
    tiktok_handle: str | None
    recruiter_visible: bool
    brand_campaigns_completed: int
    total_earnings_cents: int
    brand_average_rating: float | None
    profile_completeness_score: int
    stripe_account_id: str | None
    stripe_onboarding_complete: bool
    challenges_submitted_count: int
    challenges_converted_count: int
    badges: list[dict]
    badges_earned_count: int
    achievement_link_token: str | None
    verified_profile_public: bool
    earnings_visible_on_public_profile: bool
    enabled_tracks: list[str]
    brand_completeness_score: int
    athletic_completeness_score: int
    athletic_seasons_completed: int
    athletic_recruiter_interest_count: int
    created_at: datetime
    updated_at: datetime

    @property
    def challenge_conversion_rate(self) -> float | None:
        """Build Prompt 8G deliverable 8: derived, never stored --
        null-guarded against divide-by-zero when no submissions exist
        yet."""
        if not self.challenges_submitted_count:
            return None
        return round(self.challenges_converted_count / self.challenges_submitted_count, 2)

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "TalentProfile":
        return cls(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            display_name=row["display_name"],
            school_name=row["school_name"],
            school_type=row["school_type"],
            city=row["city"],
            state=row["state"],
            graduation_year=row["graduation_year"],
            bio=row["bio"],
            categories=list(row["categories"] or []),
            instagram_handle=row["instagram_handle"],
            tiktok_handle=row["tiktok_handle"],
            recruiter_visible=row["recruiter_visible"],
            brand_campaigns_completed=row["brand_campaigns_completed"],
            total_earnings_cents=row["total_earnings_cents"],
            brand_average_rating=float(row["brand_average_rating"]) if row["brand_average_rating"] is not None else None,
            profile_completeness_score=row["profile_completeness_score"],
            stripe_account_id=row["stripe_account_id"],
            stripe_onboarding_complete=row["stripe_onboarding_complete"],
            challenges_submitted_count=row["challenges_submitted_count"],
            challenges_converted_count=row["challenges_converted_count"],
            badges=json.loads(row["badges"]) if isinstance(row["badges"], str) else list(row["badges"] or []),
            badges_earned_count=row["badges_earned_count"],
            achievement_link_token=row["achievement_link_token"],
            verified_profile_public=row["verified_profile_public"],
            earnings_visible_on_public_profile=row["earnings_visible_on_public_profile"],
            enabled_tracks=list(row["enabled_tracks"] or []),
            brand_completeness_score=row["brand_completeness_score"],
            athletic_completeness_score=row["athletic_completeness_score"],
            athletic_seasons_completed=row["athletic_seasons_completed"],
            athletic_recruiter_interest_count=row["athletic_recruiter_interest_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


async def get_by_id(conn: asyncpg.Connection, talent_id: str) -> TalentProfile | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.talent_profiles WHERE id = $1", talent_id)
    return TalentProfile.from_row(row) if row else None


async def get_by_user_id(conn: asyncpg.Connection, user_id: str) -> TalentProfile | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.talent_profiles WHERE user_id = $1", user_id)
    return TalentProfile.from_row(row) if row else None


async def create_talent_profile(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    display_name: str,
    school_name: str,
    school_type: str | None,
    city: str,
    state: str,
    graduation_year: int,
    bio: str | None,
    categories: list[str],
    instagram_handle: str | None,
    tiktok_handle: str | None,
) -> TalentProfile:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.talent_profiles
            (user_id, display_name, school_name, school_type, city, state, graduation_year,
             bio, categories, instagram_handle, tiktok_handle)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING {_COLUMNS}
        """,
        user_id,
        display_name,
        school_name,
        school_type,
        city,
        state,
        graduation_year,
        bio,
        categories,
        instagram_handle,
        tiktok_handle,
    )
    return TalentProfile.from_row(row)


async def update_talent_profile(
    conn: asyncpg.Connection,
    talent_id: str,
    *,
    display_name: str,
    school_name: str,
    school_type: str | None,
    city: str,
    state: str,
    graduation_year: int,
    bio: str | None,
    categories: list[str],
    instagram_handle: str | None,
    tiktok_handle: str | None,
) -> TalentProfile:
    """Full-record update -- PUT /talents/me replaces every talent-writable
    field in one call. Cached/computed fields (brand_campaigns_completed,
    total_earnings_cents, brand_average_rating, profile_completeness_score,
    recruiter_visible) are deliberately absent from the parameter list:
    they are never written from this function, only from
    update_profile_completeness_score / the campaign/payout pipeline."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.talent_profiles
        SET display_name = $2, school_name = $3, school_type = $4, city = $5, state = $6,
            graduation_year = $7, bio = $8, categories = $9, instagram_handle = $10,
            tiktok_handle = $11, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        talent_id,
        display_name,
        school_name,
        school_type,
        city,
        state,
        graduation_year,
        bio,
        categories,
        instagram_handle,
        tiktok_handle,
    )
    return TalentProfile.from_row(row)


async def update_profile_completeness_score(conn: asyncpg.Connection, talent_id: str, score: int) -> None:
    await conn.execute(
        "UPDATE public.talent_profiles SET profile_completeness_score = $2, updated_at = now() WHERE id = $1",
        talent_id,
        score,
    )


async def update_brand_completeness_score(conn: asyncpg.Connection, talent_id: str, score: int) -> None:
    """D1 decision: writes brand_completeness_score and recomputes the
    cross-track profile_completeness_score (GREATEST) in the same
    statement, so the two never drift out of sync between calls."""
    await conn.execute(
        """
        UPDATE public.talent_profiles
        SET brand_completeness_score = $2,
            profile_completeness_score = GREATEST($2, athletic_completeness_score),
            updated_at = now()
        WHERE id = $1
        """,
        talent_id,
        score,
    )


async def update_athletic_completeness_score(conn: asyncpg.Connection, talent_id: str, score: int) -> None:
    """D1 decision: writes athletic_completeness_score and recomputes the
    cross-track profile_completeness_score (GREATEST) in the same
    statement."""
    await conn.execute(
        """
        UPDATE public.talent_profiles
        SET athletic_completeness_score = $2,
            profile_completeness_score = GREATEST(brand_completeness_score, $2),
            updated_at = now()
        WHERE id = $1
        """,
        talent_id,
        score,
    )


async def enable_athletic_track(conn: asyncpg.Connection, talent_id: str) -> TalentProfile:
    """POST /talents/athletics/enable (idempotent -- adding 'athletics' to
    an enabled_tracks array that already contains it is a no-op array
    append thanks to the NOT 'athletics' = ANY(...) guard)."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.talent_profiles
        SET enabled_tracks = CASE
                WHEN 'athletics' = ANY(enabled_tracks) THEN enabled_tracks
                ELSE enabled_tracks || ARRAY['athletics']::text[]
            END,
            updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        talent_id,
    )
    return TalentProfile.from_row(row)


async def recompute_athletic_cached_totals(conn: asyncpg.Connection, talent_id: str) -> None:
    """Recomputes athletic_seasons_completed, athletic_completeness_score,
    and the cross-track profile_completeness_score after an athletic
    verification event.
    D6: triggered by coach attestation completion, not payment -- see
    app/services/athletic_intelligence_service.py and ATHLETICS-4 (not
    yet wired to any route/job as of ATHLETICS-1; this function is
    correct and ready, but nothing calls it yet).
    D2: no athletic_average_rating -- stats + attestation are the
    quality signal, athletic_recruiter_interest_count is untouched here
    (that's a recruiter-engagement counter, not part of this recompute)."""
    profile = await get_by_id(conn, talent_id)
    if profile is None:
        return

    season_row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status IN ('attested', 'verified')) AS athletic_seasons_completed,
            BOOL_OR(status IN ('attested', 'verified')) AS has_attested_season
        FROM public.athletic_seasons
        WHERE talent_id = $1
        """,
        talent_id,
    )
    sport_row = await conn.fetchrow(
        """
        SELECT
            BOOL_OR(TRUE) AS has_sport_profile,
            BOOL_OR(gpa IS NOT NULL) AS has_gpa,
            BOOL_OR(hudl_url IS NOT NULL OR maxpreps_url IS NOT NULL) AS has_film_url
        FROM public.sport_profiles
        WHERE talent_id = $1
        """,
        talent_id,
    )
    nil_acknowledged = await conn.fetchval(
        """
        SELECT BOOL_OR(school_association_rules_acknowledged)
        FROM public.nil_eligibility_records
        WHERE talent_id = $1
        """,
        talent_id,
    )

    from app.core.profile_score import compute_athletic_completeness_score, compute_cross_track_score

    athletic_score = compute_athletic_completeness_score(
        has_sport_profile=bool(sport_row["has_sport_profile"]) if sport_row else False,
        has_gpa=bool(sport_row["has_gpa"]) if sport_row else False,
        has_attested_season=bool(season_row["has_attested_season"]) if season_row else False,
        has_film_url=bool(sport_row["has_film_url"]) if sport_row else False,
        nil_acknowledged=bool(nil_acknowledged),
    )
    cross_score = compute_cross_track_score(
        brand_completeness_score=profile.brand_completeness_score,
        athletic_completeness_score=athletic_score,
        enabled_tracks=profile.enabled_tracks,
    )

    await conn.execute(
        """
        UPDATE public.talent_profiles
        SET athletic_seasons_completed = $2,
            athletic_completeness_score = $3,
            profile_completeness_score = $4,
            updated_at = now()
        WHERE id = $1
        """,
        talent_id,
        season_row["athletic_seasons_completed"] if season_row else 0,
        athletic_score,
        cross_score,
    )


async def _fetch_athletic_completeness_inputs(conn: asyncpg.Connection, talent_id: str) -> dict[str, bool]:
    """Single-query fetch of the five athletic completeness inputs (D1
    decision weights) -- LEFT JOINs so a talent with zero sport_profiles/
    seasons/nil records still gets one row of all-False rather than no
    row at all."""
    row = await conn.fetchrow(
        """
        SELECT
            EXISTS (SELECT 1 FROM public.sport_profiles WHERE talent_id = $1) AS has_sport_profile,
            EXISTS (SELECT 1 FROM public.sport_profiles WHERE talent_id = $1 AND gpa IS NOT NULL) AS has_gpa,
            EXISTS (
                SELECT 1 FROM public.athletic_seasons
                WHERE talent_id = $1 AND status IN ('attested', 'verified')
            ) AS has_attested_season,
            EXISTS (
                SELECT 1 FROM public.sport_profiles
                WHERE talent_id = $1 AND (hudl_url IS NOT NULL OR maxpreps_url IS NOT NULL)
            ) AS has_film_url,
            EXISTS (
                SELECT 1 FROM public.nil_eligibility_records
                WHERE talent_id = $1 AND school_association_rules_acknowledged = TRUE
            ) AS nil_acknowledged
        """,
        talent_id,
    )
    return {
        "has_sport_profile": bool(row["has_sport_profile"]),
        "has_gpa": bool(row["has_gpa"]),
        "has_attested_season": bool(row["has_attested_season"]),
        "has_film_url": bool(row["has_film_url"]),
        "nil_acknowledged": bool(row["nil_acknowledged"]),
    }


async def recompute_all_completeness_scores(conn: asyncpg.Connection, talent_id: str) -> None:
    """Recomputes brand_completeness_score, athletic_completeness_score,
    and profile_completeness_score (cross-track GREATEST) in one call.
    Called after any state change that could affect either score --
    ATHLETICS-4 trigger wiring. Fetches brand inputs from the
    just-committed talent_profiles row and athletic inputs via
    _fetch_athletic_completeness_inputs, so a caller never needs to
    hand-assemble either score's inputs itself."""
    from app.core.profile_score import (
        compute_athletic_completeness_score,
        compute_brand_completeness_score,
        compute_cross_track_score,
    )

    profile = await get_by_id(conn, talent_id)
    if profile is None:
        return
    brand_score = compute_brand_completeness_score(
        bio=profile.bio,
        categories=profile.categories,
        school_type=profile.school_type,
        instagram_handle=profile.instagram_handle,
        tiktok_handle=profile.tiktok_handle,
        brand_campaigns_completed=profile.brand_campaigns_completed,
        badges_earned_count=profile.badges_earned_count,
    )
    athletic_inputs = await _fetch_athletic_completeness_inputs(conn, talent_id)
    athletic_score = compute_athletic_completeness_score(**athletic_inputs)
    cross_score = compute_cross_track_score(
        brand_completeness_score=brand_score,
        athletic_completeness_score=athletic_score,
        enabled_tracks=profile.enabled_tracks,
    )
    await conn.execute(
        """
        UPDATE public.talent_profiles
        SET brand_completeness_score = $2,
            athletic_completeness_score = $3,
            profile_completeness_score = $4,
            updated_at = now()
        WHERE id = $1
        """,
        talent_id,
        brand_score,
        athletic_score,
        cross_score,
    )


async def recompute_cached_totals(conn: asyncpg.Connection, talent_id: str) -> None:
    """Recomputes brand_campaigns_completed, total_earnings_cents, and
    brand_average_rating from campaign_talents (Build Prompt 10 deliverable 7).
    Section 7's schema comment leaves the mechanism open ("updated via
    trigger or background job") and Prompt 2 only produced a design
    note, never an implemented trigger (no such trigger exists in any
    migration) -- so this is application-code recompute, called from
    app/services/payout_service.handle_transfer_paid right after a
    transfer.paid webhook lands, matching this codebase's existing
    style of computing cached fields at the call site rather than in
    SQL (see update_profile_completeness_score above).
    profile_completeness_score is untouched here -- payout completion
    doesn't change what's filled in on the profile.

    Build Prompt 8B addition: total_earnings_cents also folds in paid
    milestone payouts (SUM of campaign_talent_milestones.payout_cents
    where payout_status='paid', across every campaign_talents row for
    this talent) -- a milestone campaign's campaign_talents.payout_cents
    itself is never set (each milestone is paid individually via
    campaign_talent_milestones, not one lump transfer), so leaving this
    query as flat-only would silently under-report a milestone-earning
    talent's lifetime total. brand_campaigns_completed is left as
    flat-status-'paid'-only for now (a milestone campaign's
    campaign_talents.status reaches 'confirmed', not 'paid', after its
    final milestone -- see app/routers/brands.py's confirm_milestone --
    so counting "campaigns completed" for milestone campaigns needs a
    product decision on what "completed" means there that's out of
    this recompute's scope; flagged, not silently guessed)."""
    row = await conn.fetchrow(
        """
        WITH talents AS (
            SELECT id, status, payout_cents, brand_rating FROM public.campaign_talents WHERE talent_id = $1
        ), paid_milestones AS (
            SELECT COALESCE(SUM(crm.payout_cents), 0) AS total
            FROM public.campaign_talent_milestones crm
            WHERE crm.campaign_talent_id IN (SELECT id FROM talents) AND crm.payout_status = 'paid'
        ), paid_challenge_bonuses AS (
            -- Build Prompt 8G: challenge conversion bonuses count toward
            -- lifetime earnings the same as flat/milestone campaign
            -- payouts (spec deliverable 6: "update
            -- talent_profiles.total_earnings_cents").
            SELECT COALESCE(SUM(cs.payout_cents), 0) AS total
            FROM public.challenge_submissions cs
            WHERE cs.talent_id = $1 AND cs.payout_status = 'paid'
        )
        SELECT
            (SELECT COUNT(*) FROM talents WHERE status = 'paid') AS brand_campaigns_completed,
            (SELECT COALESCE(SUM(payout_cents), 0) FROM talents WHERE status = 'paid')
              + (SELECT total FROM paid_milestones)
              + (SELECT total FROM paid_challenge_bonuses) AS total_earnings_cents,
            (SELECT AVG(brand_rating) FROM talents WHERE brand_rating IS NOT NULL) AS brand_average_rating
        """,
        talent_id,
    )
    await conn.execute(
        """
        UPDATE public.talent_profiles
        SET brand_campaigns_completed = $2, total_earnings_cents = $3, brand_average_rating = $4, updated_at = now()
        WHERE id = $1
        """,
        talent_id,
        row["brand_campaigns_completed"],
        row["total_earnings_cents"],
        row["brand_average_rating"],
    )


async def increment_challenges_submitted_count(conn: asyncpg.Connection, talent_id: str) -> None:
    await conn.execute(
        "UPDATE public.talent_profiles SET challenges_submitted_count = challenges_submitted_count + 1, updated_at = now() WHERE id = $1",
        talent_id,
    )


async def increment_challenges_converted_count(conn: asyncpg.Connection, talent_id: str) -> None:
    await conn.execute(
        "UPDATE public.talent_profiles SET challenges_converted_count = challenges_converted_count + 1, updated_at = now() WHERE id = $1",
        talent_id,
    )


async def append_badge_and_recompute_score(
    conn: asyncpg.Connection, talent_id: str, *, badge: dict, new_score: int, new_brand_score: int | None = None
) -> TalentProfile | None:
    """Atomic badge issuance (Build Prompt 8H deliverable 5g): appends
    `badge` to talent_profiles.badges, increments badges_earned_count, and
    recomputes profile_completeness_score (and, per the D1 track split,
    brand_completeness_score -- badges are a brand-track signal) in one
    UPDATE. Called inside the same transaction as
    learning_modules_repository.mark_passed -- if this UPDATE fails for
    any reason, the caller's transaction rolls back the completion
    status change too, so a talent is never left 'passed' without a badge
    (spec: "if the badges jsonb append fails, the completion status
    must not be set to 'passed'").

    new_brand_score defaults to new_score for backward compatibility
    with any caller that hasn't adopted the brand/cross-track split."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.talent_profiles
        SET badges = badges || $2::jsonb,
            badges_earned_count = badges_earned_count + 1,
            profile_completeness_score = $3,
            brand_completeness_score = $4,
            updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        talent_id,
        json.dumps([badge]),
        new_score,
        new_brand_score if new_brand_score is not None else new_score,
    )
    return TalentProfile.from_row(row) if row else None


async def get_by_stripe_account_id(conn: asyncpg.Connection, stripe_account_id: str) -> TalentProfile | None:
    """Looked up by the account.updated webhook (Build Prompt 7), which
    identifies the account by Stripe account id, not our own talent_id."""
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.talent_profiles WHERE stripe_account_id = $1", stripe_account_id)
    return TalentProfile.from_row(row) if row else None


async def get_insight_feedback_opt_in(conn: asyncpg.Connection, talent_id: str) -> bool:
    value = await conn.fetchval(
        "SELECT insight_feedback_opt_in FROM public.talent_profiles WHERE id = $1", talent_id
    )
    return bool(value)


async def set_insight_feedback_opt_in(conn: asyncpg.Connection, talent_id: str, *, opted_in: bool) -> None:
    """Build Prompt 8I: Insight & Feedback panel eligibility is opt-in,
    not automatic -- see the migration's talent_profiles.insight_feedback_opt_in
    column comment."""
    await conn.execute(
        "UPDATE public.talent_profiles SET insight_feedback_opt_in = $2, updated_at = now() WHERE id = $1",
        talent_id,
        opted_in,
    )


async def set_stripe_account_id(conn: asyncpg.Connection, talent_id: str, stripe_account_id: str) -> None:
    await conn.execute(
        "UPDATE public.talent_profiles SET stripe_account_id = $2, updated_at = now() WHERE id = $1",
        talent_id,
        stripe_account_id,
    )


async def set_stripe_onboarding_complete(conn: asyncpg.Connection, talent_id: str, complete: bool) -> None:
    await conn.execute(
        "UPDATE public.talent_profiles SET stripe_onboarding_complete = $2, updated_at = now() WHERE id = $1",
        talent_id,
        complete,
    )


@dataclass(frozen=True, slots=True)
class TalentBrowseCard:
    """GET /brands/campaigns/:id/talents/browse (Build Prompt 8 deliverable
    7, acceptance criterion "Browse endpoints never return PII"). Section
    8 doesn't give an exact field list for this endpoint the way it does
    for POST /brands/campaigns, so the field set below is a deliberate,
    conservative interpretation, not a literal spec quote -- flagged the
    same way docs/parent_records_creation_timing.md flags an interpreted
    gap.

    Excluded on purpose: display_name, school_name (a specific school
    name is quasi-identifying combined with city/state), bio (free text
    could contain anything), instagram_handle/tiktok_handle. A brand
    only sees enough to judge fit (location, categories, school type,
    completeness, track record) -- identity is revealed only once the
    brand actually invites a specific talent_id, the same "browse costs
    nothing, revealing identity is a deliberate act" shape Section 8
    uses for GET /recruiters/talents/search vs GET /recruiters/talents/:id."""

    talent_id: str
    city: str
    state: str
    graduation_year: int
    school_type: str | None
    categories: list[str]
    profile_completeness_score: int
    brand_average_rating: float | None
    brand_campaigns_completed: int
    challenges_converted_count: int = 0
    challenge_conversion_rate: float | None = None
    badge_count: int = 0
    badge_titles: list = None


@dataclass(frozen=True, slots=True)
class RecruiterSearchCard:
    """GET /recruiters/talents/search (Build Prompt 11 deliverable 2,
    acceptance criterion "search never returns identifying fields
    before credit spent"). Same no-PII field set as TalentBrowseCard --
    reused as its own dataclass (not TalentBrowseCard itself) since the
    two searches filter on different, independently evolving param
    sets (brand: categories/city off a campaign; recruiter: graduation
    year/city/state/categories/min_campaigns/min_rating) and shouldn't
    be forced to share a query function just because today's field
    list happens to match."""

    talent_id: str
    city: str
    state: str
    graduation_year: int
    school_type: str | None
    categories: list[str]
    profile_completeness_score: int
    brand_average_rating: float | None
    brand_campaigns_completed: int
    challenges_converted_count: int = 0
    challenge_conversion_rate: float | None = None
    badge_count: int = 0
    badge_titles: list = None


async def search_for_recruiter(
    conn: asyncpg.Connection,
    *,
    graduation_year: int | None,
    city: str | None,
    state: str | None,
    categories: list[str] | None,
    min_campaigns: int | None,
    min_rating: float | None,
    limit: int,
    offset: int,
) -> list[RecruiterSearchCard]:
    rows = await conn.fetch(
        """
        SELECT id, city, state, graduation_year, school_type, categories,
               profile_completeness_score, brand_average_rating, brand_campaigns_completed,
               challenges_submitted_count, challenges_converted_count, badges, badges_earned_count
        FROM public.talent_profiles
        WHERE recruiter_visible = TRUE
          AND ($1::int IS NULL OR graduation_year = $1)
          AND ($2::text IS NULL OR city = $2)
          AND ($3::text IS NULL OR state = $3)
          AND ($4::text[] IS NULL OR categories && $4::text[])
          AND ($5::int IS NULL OR brand_campaigns_completed >= $5)
          AND ($6::numeric IS NULL OR brand_average_rating >= $6)
        ORDER BY profile_completeness_score DESC
        LIMIT $7 OFFSET $8
        """,
        graduation_year,
        city,
        state,
        categories or None,
        min_campaigns,
        min_rating,
        limit,
        offset,
    )
    return [
        RecruiterSearchCard(
            talent_id=str(row["id"]),
            city=row["city"],
            state=row["state"],
            graduation_year=row["graduation_year"],
            school_type=row["school_type"],
            categories=list(row["categories"] or []),
            profile_completeness_score=row["profile_completeness_score"],
            brand_average_rating=float(row["brand_average_rating"]) if row["brand_average_rating"] is not None else None,
            brand_campaigns_completed=row["brand_campaigns_completed"],
            challenges_converted_count=row["challenges_converted_count"],
            challenge_conversion_rate=(
                round(row["challenges_converted_count"] / row["challenges_submitted_count"], 2)
                if row["challenges_submitted_count"]
                else None
            ),
            badge_count=row["badges_earned_count"],
            badge_titles=[b["badge_title"] for b in (json.loads(row["badges"]) if isinstance(row["badges"], str) else (row["badges"] or []))],
        )
        for row in rows
    ]


@dataclass(frozen=True, slots=True)
class AthleticRecruiterSearchCard:
    """GET /recruiters/talents/search?track=athletics (ATHLETICS-5).
    No-PII field set, athletic-specific -- not reused from
    RecruiterSearchCard since the two searches filter/order on
    independently evolving athletic vs. brand fields."""

    talent_id: str
    city: str
    state: str
    graduation_year: int
    school_type: str | None
    categories: list[str]
    athletic_completeness_score: int
    athletic_seasons_completed: int
    athletic_recruiter_interest_count: int
    sports: list[str]
    top_sport_positions: list[str]
    top_sport_gpa: float | None
    has_film_url: bool


async def search_for_athletic_recruiter(
    conn: asyncpg.Connection,
    *,
    sports: list[str] | None,
    min_seasons: int | None,
    limit: int,
    offset: int,
) -> list[AthleticRecruiterSearchCard]:
    """"Top sport" (for top_sport_positions/top_sport_gpa) is the sport
    with the most attested/verified seasons for that talent, ties broken
    alphabetically; a talent with sport_profiles but zero seasons still
    gets a deterministic top sport (attested_count=0 for all, alpha
    order wins)."""
    rows = await conn.fetch(
        """
        WITH sport_activity AS (
            SELECT sp.talent_id, sp.sport, sp.positions, sp.gpa,
                   COALESCE(sc.attested_count, 0) AS attested_count
            FROM public.sport_profiles sp
            LEFT JOIN (
                SELECT talent_id, sport,
                       COUNT(*) FILTER (WHERE status IN ('attested', 'verified')) AS attested_count
                FROM public.athletic_seasons
                GROUP BY talent_id, sport
            ) sc ON sc.talent_id = sp.talent_id AND sc.sport = sp.sport
        ),
        top_sport AS (
            SELECT DISTINCT ON (talent_id)
                talent_id, positions AS top_sport_positions, gpa AS top_sport_gpa
            FROM sport_activity
            ORDER BY talent_id, attested_count DESC, sport
        ),
        sport_agg AS (
            SELECT talent_id,
                   array_agg(DISTINCT sport ORDER BY sport) AS sports,
                   BOOL_OR(hudl_url IS NOT NULL OR maxpreps_url IS NOT NULL) AS has_film_url
            FROM public.sport_profiles
            GROUP BY talent_id
        )
        SELECT
            tp.id, tp.city, tp.state, tp.graduation_year, tp.school_type, tp.categories,
            tp.athletic_completeness_score, tp.athletic_seasons_completed, tp.athletic_recruiter_interest_count,
            COALESCE(sa.sports, ARRAY[]::text[]) AS sports,
            COALESCE(sa.has_film_url, FALSE) AS has_film_url,
            COALESCE(ts.top_sport_positions, ARRAY[]::text[]) AS top_sport_positions,
            ts.top_sport_gpa
        FROM public.talent_profiles tp
        LEFT JOIN sport_agg sa ON sa.talent_id = tp.id
        LEFT JOIN top_sport ts ON ts.talent_id = tp.id
        WHERE tp.recruiter_visible = TRUE
          AND 'athletics' = ANY(tp.enabled_tracks)
          AND ($1::text[] IS NULL OR sa.sports && $1::text[])
          AND ($2::int IS NULL OR tp.athletic_seasons_completed >= $2)
        ORDER BY tp.athletic_completeness_score DESC
        LIMIT $3 OFFSET $4
        """,
        sports or None,
        min_seasons,
        limit,
        offset,
    )
    return [
        AthleticRecruiterSearchCard(
            talent_id=str(row["id"]),
            city=row["city"],
            state=row["state"],
            graduation_year=row["graduation_year"],
            school_type=row["school_type"],
            categories=list(row["categories"] or []),
            athletic_completeness_score=row["athletic_completeness_score"],
            athletic_seasons_completed=row["athletic_seasons_completed"],
            athletic_recruiter_interest_count=row["athletic_recruiter_interest_count"],
            sports=list(row["sports"] or []),
            top_sport_positions=list(row["top_sport_positions"] or []),
            top_sport_gpa=float(row["top_sport_gpa"]) if row["top_sport_gpa"] is not None else None,
            has_film_url=bool(row["has_film_url"]),
        )
        for row in rows
    ]


async def increment_athletic_recruiter_interest(conn: asyncpg.Connection, talent_id: str) -> None:
    """D2 engagement signal (ATHLETICS-5): a recruiter spending a credit
    to view, or saving, an athletic-track talent's profile. Never
    decremented on unsave/unview -- interest was genuine when expressed."""
    await conn.execute(
        "UPDATE public.talent_profiles SET athletic_recruiter_interest_count = athletic_recruiter_interest_count + 1, "
        "updated_at = now() WHERE id = $1",
        talent_id,
    )


async def browse_for_brand(
    conn: asyncpg.Connection, *, categories: list[str], city: str | None
) -> list[TalentBrowseCard]:
    """Matches on target_categories overlap the same way
    list_available_for_rep matches campaigns to talents (the inverse
    direction) -- only recruiter_visible talents are eligible, since that
    flag is the talent's own opt-in to being discoverable at all (Section
    7), not something a brand's search can bypass."""
    rows = await conn.fetch(
        """
        SELECT id, city, state, graduation_year, school_type, categories,
               profile_completeness_score, brand_average_rating, brand_campaigns_completed,
               challenges_submitted_count, challenges_converted_count, badges, badges_earned_count
        FROM public.talent_profiles
        WHERE recruiter_visible = TRUE
          AND ($1::text[] IS NULL OR categories && $1::text[])
          AND ($2::text IS NULL OR city = $2)
        ORDER BY profile_completeness_score DESC
        """,
        categories or None,
        city,
    )
    return [
        TalentBrowseCard(
            talent_id=str(row["id"]),
            city=row["city"],
            state=row["state"],
            graduation_year=row["graduation_year"],
            school_type=row["school_type"],
            categories=list(row["categories"] or []),
            profile_completeness_score=row["profile_completeness_score"],
            brand_average_rating=float(row["brand_average_rating"]) if row["brand_average_rating"] is not None else None,
            brand_campaigns_completed=row["brand_campaigns_completed"],
            challenges_converted_count=row["challenges_converted_count"],
            challenge_conversion_rate=(
                round(row["challenges_converted_count"] / row["challenges_submitted_count"], 2)
                if row["challenges_submitted_count"]
                else None
            ),
            badge_count=row["badges_earned_count"],
            badge_titles=[b["badge_title"] for b in (json.loads(row["badges"]) if isinstance(row["badges"], str) else (row["badges"] or []))],
        )
        for row in rows
    ]


async def get_or_create_achievement_link_token(conn: asyncpg.Connection, talent_id: str) -> str:
    """Build Prompt 5 deliverable 12: the token is generated once and
    never regenerated (spec: "the same URL works forever"), so this
    reads first and only writes on a genuine first call -- a second
    call for the same talent is a no-op read, not a fresh secrets.token_urlsafe
    call that would silently orphan a previously-shared link."""
    existing = await conn.fetchval("SELECT achievement_link_token FROM public.talent_profiles WHERE id = $1", talent_id)
    if existing:
        return existing
    token = secrets.token_urlsafe(24)  # 24 raw bytes -> 32 URL-safe base64 chars, matching the spec's "32-character" token
    await conn.execute(
        "UPDATE public.talent_profiles SET achievement_link_token = $2, updated_at = now() WHERE id = $1",
        talent_id,
        token,
    )
    return token


async def update_achievement_link_visibility(
    conn: asyncpg.Connection, talent_id: str, *, verified_profile_public: bool, earnings_visible_on_public_profile: bool
) -> TalentProfile:
    row = await conn.fetchrow(
        f"""
        UPDATE public.talent_profiles
        SET verified_profile_public = $2, earnings_visible_on_public_profile = $3, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        talent_id,
        verified_profile_public,
        earnings_visible_on_public_profile,
    )
    return TalentProfile.from_row(row)


@dataclass(frozen=True, slots=True)
class PublicVerifiedProfile:
    """Deliberately its own type, not a reuse of TalentProfile -- the
    public /verified/:token route (Build Prompt 5 deliverable 12) must
    be structurally incapable of leaking a field this type doesn't
    declare (Instagram/TikTok handles, bio, submission content,
    recruiter messages, parent info), regardless of what the SELECT
    below happens to fetch."""

    id: str
    display_name: str
    school_name: str
    graduation_year: int
    city: str
    categories: list[str]
    badges: list[dict]
    brand_campaigns_completed: int
    brand_average_rating: float | None
    total_earnings_cents: int | None  # None when earnings_visible_on_public_profile is False
    verified_profile_public: bool
    enabled_tracks: list[str]
    updated_at: datetime


async def get_public_profile_by_token(conn: asyncpg.Connection, token: str) -> PublicVerifiedProfile | None:
    """Returns None only when the token itself doesn't exist (404 case).
    A talent who has the token but has verified_profile_public = FALSE
    still gets a row back here -- the router is what turns that into
    the "not currently public" response (spec: not a 404, since the
    talent may share the link before flipping visibility on)."""
    row = await conn.fetchrow(
        """
        SELECT id, display_name, school_name, graduation_year, city, categories, badges,
               brand_campaigns_completed, brand_average_rating, total_earnings_cents,
               verified_profile_public, earnings_visible_on_public_profile, enabled_tracks, updated_at
        FROM public.talent_profiles
        WHERE achievement_link_token = $1
        """,
        token,
    )
    if row is None:
        return None
    return PublicVerifiedProfile(
        id=str(row["id"]),
        display_name=row["display_name"],
        school_name=row["school_name"],
        graduation_year=row["graduation_year"],
        city=row["city"],
        categories=list(row["categories"] or []),
        badges=json.loads(row["badges"]) if isinstance(row["badges"], str) else list(row["badges"] or []),
        brand_campaigns_completed=row["brand_campaigns_completed"],
        brand_average_rating=float(row["brand_average_rating"]) if row["brand_average_rating"] is not None else None,
        total_earnings_cents=row["total_earnings_cents"] if row["earnings_visible_on_public_profile"] else None,
        verified_profile_public=row["verified_profile_public"],
        enabled_tracks=list(row["enabled_tracks"] or []),
        updated_at=row["updated_at"],
    )
