"""Data access for public.rep_profiles.

Follows the same shape as users_repository.py / parent_records_repository.py:
every function takes an explicit asyncpg connection, frozen/slots
dataclass with `from_row`, jsonb-free here since `categories` is a
Postgres TEXT[] (asyncpg maps it to a Python list directly, no
json.dumps/loads needed, unlike parent_records.values_filters which is
JSONB).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

_COLUMNS = (
    "id, user_id, display_name, school_name, school_type, city, state, graduation_year, "
    "bio, categories, instagram_handle, tiktok_handle, recruiter_visible, "
    "total_campaigns_completed, total_earnings_cents, average_rating, "
    "profile_completeness_score, created_at, updated_at"
)


@dataclass(frozen=True, slots=True)
class RepProfile:
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
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "RepProfile":
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
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


async def get_by_id(conn: asyncpg.Connection, rep_id: str) -> RepProfile | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.rep_profiles WHERE id = $1", rep_id)
    return RepProfile.from_row(row) if row else None


async def get_by_user_id(conn: asyncpg.Connection, user_id: str) -> RepProfile | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.rep_profiles WHERE user_id = $1", user_id)
    return RepProfile.from_row(row) if row else None


async def create_rep_profile(
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
) -> RepProfile:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.rep_profiles
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
    return RepProfile.from_row(row)


async def update_rep_profile(
    conn: asyncpg.Connection,
    rep_id: str,
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
) -> RepProfile:
    """Full-record update -- PUT /reps/me replaces every rep-writable
    field in one call. Cached/computed fields (total_campaigns_completed,
    total_earnings_cents, average_rating, profile_completeness_score,
    recruiter_visible) are deliberately absent from the parameter list:
    they are never written from this function, only from
    update_profile_completeness_score / the campaign/payout pipeline."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.rep_profiles
        SET display_name = $2, school_name = $3, school_type = $4, city = $5, state = $6,
            graduation_year = $7, bio = $8, categories = $9, instagram_handle = $10,
            tiktok_handle = $11, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        rep_id,
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
    return RepProfile.from_row(row)


async def update_profile_completeness_score(conn: asyncpg.Connection, rep_id: str, score: int) -> None:
    await conn.execute(
        "UPDATE public.rep_profiles SET profile_completeness_score = $2, updated_at = now() WHERE id = $1",
        rep_id,
        score,
    )
