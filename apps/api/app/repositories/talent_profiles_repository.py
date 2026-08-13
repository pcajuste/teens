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
    "total_campaigns_completed, total_earnings_cents, average_rating, "
    "profile_completeness_score, stripe_account_id, stripe_onboarding_complete, "
    "challenges_submitted_count, challenges_converted_count, badges, badges_earned_count, "
    "achievement_link_token, verified_profile_public, earnings_visible_on_public_profile, "
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
    total_campaigns_completed: int
    total_earnings_cents: int
    average_rating: float | None
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
            total_campaigns_completed=row["total_campaigns_completed"],
            total_earnings_cents=row["total_earnings_cents"],
            average_rating=float(row["average_rating"]) if row["average_rating"] is not None else None,
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
    field in one call. Cached/computed fields (total_campaigns_completed,
    total_earnings_cents, average_rating, profile_completeness_score,
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


async def recompute_cached_totals(conn: asyncpg.Connection, talent_id: str) -> None:
    """Recomputes total_campaigns_completed, total_earnings_cents, and
    average_rating from campaign_talents (Build Prompt 10 deliverable 7).
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
    talent's lifetime total. total_campaigns_completed is left as
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
            (SELECT COUNT(*) FROM talents WHERE status = 'paid') AS total_campaigns_completed,
            (SELECT COALESCE(SUM(payout_cents), 0) FROM talents WHERE status = 'paid')
              + (SELECT total FROM paid_milestones)
              + (SELECT total FROM paid_challenge_bonuses) AS total_earnings_cents,
            (SELECT AVG(brand_rating) FROM talents WHERE brand_rating IS NOT NULL) AS average_rating
        """,
        talent_id,
    )
    await conn.execute(
        """
        UPDATE public.talent_profiles
        SET total_campaigns_completed = $2, total_earnings_cents = $3, average_rating = $4, updated_at = now()
        WHERE id = $1
        """,
        talent_id,
        row["total_campaigns_completed"],
        row["total_earnings_cents"],
        row["average_rating"],
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
    conn: asyncpg.Connection, talent_id: str, *, badge: dict, new_score: int
) -> TalentProfile | None:
    """Atomic badge issuance (Build Prompt 8H deliverable 5g): appends
    `badge` to talent_profiles.badges, increments badges_earned_count, and
    recomputes profile_completeness_score in one UPDATE. Called inside
    the same transaction as
    learning_modules_repository.mark_passed -- if this UPDATE fails for
    any reason, the caller's transaction rolls back the completion
    status change too, so a talent is never left 'passed' without a badge
    (spec: "if the badges jsonb append fails, the completion status
    must not be set to 'passed'")."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.talent_profiles
        SET badges = badges || $2::jsonb,
            badges_earned_count = badges_earned_count + 1,
            profile_completeness_score = $3,
            updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        talent_id,
        json.dumps([badge]),
        new_score,
    )
    return TalentProfile.from_row(row) if row else None


async def get_by_stripe_account_id(conn: asyncpg.Connection, stripe_account_id: str) -> TalentProfile | None:
    """Looked up by the account.updated webhook (Build Prompt 7), which
    identifies the account by Stripe account id, not our own talent_id."""
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.talent_profiles WHERE stripe_account_id = $1", stripe_account_id)
    return TalentProfile.from_row(row) if row else None


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
    average_rating: float | None
    total_campaigns_completed: int
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
    average_rating: float | None
    total_campaigns_completed: int
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
               profile_completeness_score, average_rating, total_campaigns_completed,
               challenges_submitted_count, challenges_converted_count, badges, badges_earned_count
        FROM public.talent_profiles
        WHERE recruiter_visible = TRUE
          AND ($1::int IS NULL OR graduation_year = $1)
          AND ($2::text IS NULL OR city = $2)
          AND ($3::text IS NULL OR state = $3)
          AND ($4::text[] IS NULL OR categories && $4::text[])
          AND ($5::int IS NULL OR total_campaigns_completed >= $5)
          AND ($6::numeric IS NULL OR average_rating >= $6)
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
            average_rating=float(row["average_rating"]) if row["average_rating"] is not None else None,
            total_campaigns_completed=row["total_campaigns_completed"],
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
               profile_completeness_score, average_rating, total_campaigns_completed,
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
            average_rating=float(row["average_rating"]) if row["average_rating"] is not None else None,
            total_campaigns_completed=row["total_campaigns_completed"],
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

    display_name: str
    school_name: str
    graduation_year: int
    city: str
    categories: list[str]
    badges: list[dict]
    total_campaigns_completed: int
    average_rating: float | None
    total_earnings_cents: int | None  # None when earnings_visible_on_public_profile is False
    verified_profile_public: bool
    updated_at: datetime


async def get_public_profile_by_token(conn: asyncpg.Connection, token: str) -> PublicVerifiedProfile | None:
    """Returns None only when the token itself doesn't exist (404 case).
    A talent who has the token but has verified_profile_public = FALSE
    still gets a row back here -- the router is what turns that into
    the "not currently public" response (spec: not a 404, since the
    talent may share the link before flipping visibility on)."""
    row = await conn.fetchrow(
        """
        SELECT display_name, school_name, graduation_year, city, categories, badges,
               total_campaigns_completed, average_rating, total_earnings_cents,
               verified_profile_public, earnings_visible_on_public_profile, updated_at
        FROM public.talent_profiles
        WHERE achievement_link_token = $1
        """,
        token,
    )
    if row is None:
        return None
    return PublicVerifiedProfile(
        display_name=row["display_name"],
        school_name=row["school_name"],
        graduation_year=row["graduation_year"],
        city=row["city"],
        categories=list(row["categories"] or []),
        badges=json.loads(row["badges"]) if isinstance(row["badges"], str) else list(row["badges"] or []),
        total_campaigns_completed=row["total_campaigns_completed"],
        average_rating=float(row["average_rating"]) if row["average_rating"] is not None else None,
        total_earnings_cents=row["total_earnings_cents"] if row["earnings_visible_on_public_profile"] else None,
        verified_profile_public=row["verified_profile_public"],
        updated_at=row["updated_at"],
    )
