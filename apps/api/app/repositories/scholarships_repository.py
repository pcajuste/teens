"""Data access for public.scholarships / public.scholarship_applications
(Build Prompt 8I template 2)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import asyncpg

_COLUMNS = (
    "id, brand_id, title, award_amount_cents, number_of_awards, eligibility_criteria, "
    "application_requirements, why_text, image_url, video_url, deadline, "
    "moderation_status, reviewed_by, reviewed_at, rejection_reason, status, created_at, updated_at"
)


def _load_criteria(raw) -> list[dict]:
    return json.loads(raw) if isinstance(raw, str) else list(raw or [])


@dataclass(frozen=True, slots=True)
class Scholarship:
    id: str
    brand_id: str
    title: str
    award_amount_cents: int
    number_of_awards: int
    eligibility_criteria: list[dict]
    application_requirements: str
    why_text: str
    image_url: str | None
    video_url: str | None
    deadline: datetime
    moderation_status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "Scholarship":
        return cls(
            id=str(row["id"]),
            brand_id=str(row["brand_id"]),
            title=row["title"],
            award_amount_cents=row["award_amount_cents"],
            number_of_awards=row["number_of_awards"],
            eligibility_criteria=_load_criteria(row["eligibility_criteria"]),
            application_requirements=row["application_requirements"],
            why_text=row["why_text"],
            image_url=row["image_url"],
            video_url=row["video_url"],
            deadline=row["deadline"],
            moderation_status=row["moderation_status"],
            reviewed_by=str(row["reviewed_by"]) if row["reviewed_by"] else None,
            reviewed_at=row["reviewed_at"],
            rejection_reason=row["rejection_reason"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


async def create(
    conn: asyncpg.Connection,
    *,
    brand_id: str,
    title: str,
    award_amount_cents: int,
    number_of_awards: int,
    eligibility_criteria: list[dict],
    application_requirements: str,
    why_text: str,
    image_url: str | None,
    video_url: str | None,
    deadline: datetime,
) -> Scholarship:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.scholarships
          (brand_id, title, award_amount_cents, number_of_awards, eligibility_criteria,
           application_requirements, why_text, image_url, video_url, deadline)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9, $10)
        RETURNING {_COLUMNS}
        """,
        brand_id,
        title,
        award_amount_cents,
        number_of_awards,
        json.dumps(eligibility_criteria),
        application_requirements,
        why_text,
        image_url,
        video_url,
        deadline,
    )
    return Scholarship.from_row(row)


async def get_by_id(conn: asyncpg.Connection, scholarship_id: str) -> Scholarship | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.scholarships WHERE id = $1", scholarship_id)
    return Scholarship.from_row(row) if row else None


async def get_by_id_and_brand(conn: asyncpg.Connection, scholarship_id: str, brand_id: str) -> Scholarship | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.scholarships WHERE id = $1 AND brand_id = $2", scholarship_id, brand_id
    )
    return Scholarship.from_row(row) if row else None


async def list_for_brand(conn: asyncpg.Connection, brand_id: str) -> list[Scholarship]:
    rows = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.scholarships WHERE brand_id = $1 ORDER BY created_at DESC", brand_id
    )
    return [Scholarship.from_row(r) for r in rows]


async def list_active(conn: asyncpg.Connection) -> list[Scholarship]:
    """Talent-facing browse -- only status='active' rows, which can
    only exist if moderation_status='approved' (DB constraint
    scholarships_live_requires_approval)."""
    rows = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.scholarships WHERE status = 'active' ORDER BY deadline ASC"
    )
    return [Scholarship.from_row(r) for r in rows]


async def submit_for_review(conn: asyncpg.Connection, scholarship_id: str) -> Scholarship:
    row = await conn.fetchrow(
        f"""
        UPDATE public.scholarships SET moderation_status = 'pending_review', updated_at = now()
        WHERE id = $1 RETURNING {_COLUMNS}
        """,
        scholarship_id,
    )
    return Scholarship.from_row(row)


async def review(
    conn: asyncpg.Connection, scholarship_id: str, *, approved: bool, reviewer_id: str, rejection_reason: str | None
) -> Scholarship:
    row = await conn.fetchrow(
        f"""
        UPDATE public.scholarships
        SET moderation_status = $2, reviewed_by = $3, reviewed_at = now(),
            rejection_reason = $4, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        scholarship_id,
        "approved" if approved else "rejected",
        reviewer_id,
        rejection_reason,
    )
    return Scholarship.from_row(row)


async def activate(conn: asyncpg.Connection, scholarship_id: str) -> Scholarship:
    """Brand-triggered go-live. The DB CHECK constraint
    (scholarships_live_requires_approval) is the actual backstop; the
    router still pre-checks moderation_status itself so it can return a
    clean 400 rather than surfacing a raw constraint violation."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.scholarships SET status = 'active', updated_at = now()
        WHERE id = $1 RETURNING {_COLUMNS}
        """,
        scholarship_id,
    )
    return Scholarship.from_row(row)


async def close(conn: asyncpg.Connection, scholarship_id: str) -> Scholarship:
    row = await conn.fetchrow(
        f"""
        UPDATE public.scholarships SET status = 'closed', updated_at = now()
        WHERE id = $1 RETURNING {_COLUMNS}
        """,
        scholarship_id,
    )
    return Scholarship.from_row(row)


async def list_pending_review(conn: asyncpg.Connection) -> list[Scholarship]:
    rows = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.scholarships WHERE moderation_status = 'pending_review' ORDER BY created_at ASC"
    )
    return [Scholarship.from_row(r) for r in rows]


# ──────────────────────────────────────────────────────────────────
# scholarship_applications
# ──────────────────────────────────────────────────────────────────

_APP_COLUMNS = "id, scholarship_id, talent_id, response_text, status, submitted_at, reviewed_at"


@dataclass(frozen=True, slots=True)
class ScholarshipApplication:
    id: str
    scholarship_id: str
    talent_id: str
    response_text: str
    status: str
    submitted_at: datetime
    reviewed_at: datetime | None

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "ScholarshipApplication":
        return cls(
            id=str(row["id"]),
            scholarship_id=str(row["scholarship_id"]),
            talent_id=str(row["talent_id"]),
            response_text=row["response_text"],
            status=row["status"],
            submitted_at=row["submitted_at"],
            reviewed_at=row["reviewed_at"],
        )


async def apply(
    conn: asyncpg.Connection, *, scholarship_id: str, talent_id: str, response_text: str
) -> ScholarshipApplication:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.scholarship_applications (scholarship_id, talent_id, response_text)
        VALUES ($1, $2, $3)
        RETURNING {_APP_COLUMNS}
        """,
        scholarship_id,
        talent_id,
        response_text,
    )
    return ScholarshipApplication.from_row(row)


async def has_applied(conn: asyncpg.Connection, *, scholarship_id: str, talent_id: str) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM public.scholarship_applications WHERE scholarship_id = $1 AND talent_id = $2",
        scholarship_id,
        talent_id,
    )
    return row is not None


async def list_for_talent(conn: asyncpg.Connection, talent_id: str) -> list[ScholarshipApplication]:
    rows = await conn.fetch(
        f"SELECT {_APP_COLUMNS} FROM public.scholarship_applications WHERE talent_id = $1 ORDER BY submitted_at DESC",
        talent_id,
    )
    return [ScholarshipApplication.from_row(r) for r in rows]


async def list_for_scholarship(conn: asyncpg.Connection, scholarship_id: str) -> list[ScholarshipApplication]:
    rows = await conn.fetch(
        f"SELECT {_APP_COLUMNS} FROM public.scholarship_applications WHERE scholarship_id = $1 ORDER BY submitted_at ASC",
        scholarship_id,
    )
    return [ScholarshipApplication.from_row(r) for r in rows]


async def set_application_status(conn: asyncpg.Connection, application_id: str, status: str) -> ScholarshipApplication:
    row = await conn.fetchrow(
        f"""
        UPDATE public.scholarship_applications SET status = $2, reviewed_at = now()
        WHERE id = $1 RETURNING {_APP_COLUMNS}
        """,
        application_id,
        status,
    )
    return ScholarshipApplication.from_row(row)


async def parent_dashboard_activity(conn: asyncpg.Connection, talent_id: str) -> dict:
    """GET /parent/dashboard's scholarship_activity block. Mirrors
    challenges_repository.parent_dashboard_activity's shape: totals plus a
    short recent list, no rejection-reason detail exposed to the parent."""
    totals = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total_applied,
            COUNT(*) FILTER (WHERE sa.status = 'awarded') AS total_awarded,
            COALESCE(SUM(s.award_amount_cents) FILTER (WHERE sa.status = 'awarded'), 0) AS total_awarded_cents
        FROM public.scholarship_applications sa
        JOIN public.scholarships s ON s.id = sa.scholarship_id
        WHERE sa.talent_id = $1
        """,
        talent_id,
    )
    recent = await conn.fetch(
        """
        SELECT sa.status, sa.submitted_at, s.title AS scholarship_title, s.award_amount_cents
        FROM public.scholarship_applications sa
        JOIN public.scholarships s ON s.id = sa.scholarship_id
        WHERE sa.talent_id = $1
        ORDER BY sa.submitted_at DESC
        LIMIT 5
        """,
        talent_id,
    )
    return {
        "total_applied": totals["total_applied"],
        "total_awarded": totals["total_awarded"],
        "total_awarded_cents": totals["total_awarded_cents"],
        "recent_applications": [
            {
                "scholarship_title": r["scholarship_title"],
                "submitted_at": r["submitted_at"],
                "status": r["status"],
                "award_amount_cents": r["award_amount_cents"] if r["status"] == "awarded" else None,
            }
            for r in recent
        ],
    }
