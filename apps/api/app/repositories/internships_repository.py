"""Data access for public.internships / public.internship_applications
(Build Prompt 8I template 4 -- issue #50). Mirrors
scholarships_repository.py's shape exactly."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

_COLUMNS = (
    "id, brand_id, role_title, description, time_commitment, compensation_type, compensation_why, "
    "requirements_text, application_process_text, why_text, deadline, "
    "moderation_status, reviewed_by, reviewed_at, rejection_reason, status, created_at, updated_at"
)


@dataclass(frozen=True, slots=True)
class Internship:
    id: str
    brand_id: str
    role_title: str
    description: str
    time_commitment: str
    compensation_type: str
    compensation_why: str
    requirements_text: str
    application_process_text: str
    why_text: str
    deadline: datetime
    moderation_status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "Internship":
        return cls(
            id=str(row["id"]),
            brand_id=str(row["brand_id"]),
            role_title=row["role_title"],
            description=row["description"],
            time_commitment=row["time_commitment"],
            compensation_type=row["compensation_type"],
            compensation_why=row["compensation_why"],
            requirements_text=row["requirements_text"],
            application_process_text=row["application_process_text"],
            why_text=row["why_text"],
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
    role_title: str,
    description: str,
    time_commitment: str,
    compensation_type: str,
    compensation_why: str,
    requirements_text: str,
    application_process_text: str,
    why_text: str,
    deadline: datetime,
) -> Internship:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.internships
          (brand_id, role_title, description, time_commitment, compensation_type, compensation_why,
           requirements_text, application_process_text, why_text, deadline)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING {_COLUMNS}
        """,
        brand_id,
        role_title,
        description,
        time_commitment,
        compensation_type,
        compensation_why,
        requirements_text,
        application_process_text,
        why_text,
        deadline,
    )
    return Internship.from_row(row)


async def get_by_id(conn: asyncpg.Connection, internship_id: str) -> Internship | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.internships WHERE id = $1", internship_id)
    return Internship.from_row(row) if row else None


async def get_by_id_and_brand(conn: asyncpg.Connection, internship_id: str, brand_id: str) -> Internship | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.internships WHERE id = $1 AND brand_id = $2", internship_id, brand_id
    )
    return Internship.from_row(row) if row else None


async def list_for_brand(conn: asyncpg.Connection, brand_id: str) -> list[Internship]:
    rows = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.internships WHERE brand_id = $1 ORDER BY created_at DESC", brand_id
    )
    return [Internship.from_row(r) for r in rows]


async def list_active(conn: asyncpg.Connection) -> list[Internship]:
    """Talent-facing browse -- only status='active' rows, which can
    only exist if moderation_status='approved' (DB constraint
    internships_live_requires_approval)."""
    rows = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.internships WHERE status = 'active' ORDER BY deadline ASC"
    )
    return [Internship.from_row(r) for r in rows]


async def submit_for_review(conn: asyncpg.Connection, internship_id: str) -> Internship:
    row = await conn.fetchrow(
        f"""
        UPDATE public.internships SET moderation_status = 'pending_review', updated_at = now()
        WHERE id = $1 RETURNING {_COLUMNS}
        """,
        internship_id,
    )
    return Internship.from_row(row)


async def review(
    conn: asyncpg.Connection, internship_id: str, *, approved: bool, reviewer_id: str, rejection_reason: str | None
) -> Internship:
    row = await conn.fetchrow(
        f"""
        UPDATE public.internships
        SET moderation_status = $2, reviewed_by = $3, reviewed_at = now(),
            rejection_reason = $4, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        internship_id,
        "approved" if approved else "rejected",
        reviewer_id,
        rejection_reason,
    )
    return Internship.from_row(row)


async def activate(conn: asyncpg.Connection, internship_id: str) -> Internship:
    """Brand-triggered go-live. The DB CHECK constraint
    (internships_live_requires_approval) is the actual backstop; the
    router still pre-checks moderation_status itself so it can return a
    clean 400 rather than surfacing a raw constraint violation."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.internships SET status = 'active', updated_at = now()
        WHERE id = $1 RETURNING {_COLUMNS}
        """,
        internship_id,
    )
    return Internship.from_row(row)


async def close(conn: asyncpg.Connection, internship_id: str) -> Internship:
    row = await conn.fetchrow(
        f"""
        UPDATE public.internships SET status = 'closed', updated_at = now()
        WHERE id = $1 RETURNING {_COLUMNS}
        """,
        internship_id,
    )
    return Internship.from_row(row)


async def list_pending_review(conn: asyncpg.Connection) -> list[Internship]:
    rows = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.internships WHERE moderation_status = 'pending_review' ORDER BY created_at ASC"
    )
    return [Internship.from_row(r) for r in rows]


# ──────────────────────────────────────────────────────────────────
# internship_applications
# ──────────────────────────────────────────────────────────────────

_APP_COLUMNS = "id, internship_id, talent_id, response_text, status, submitted_at, reviewed_at"


@dataclass(frozen=True, slots=True)
class InternshipApplication:
    id: str
    internship_id: str
    talent_id: str
    response_text: str
    status: str
    submitted_at: datetime
    reviewed_at: datetime | None

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "InternshipApplication":
        return cls(
            id=str(row["id"]),
            internship_id=str(row["internship_id"]),
            talent_id=str(row["talent_id"]),
            response_text=row["response_text"],
            status=row["status"],
            submitted_at=row["submitted_at"],
            reviewed_at=row["reviewed_at"],
        )


async def apply(
    conn: asyncpg.Connection, *, internship_id: str, talent_id: str, response_text: str
) -> InternshipApplication:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.internship_applications (internship_id, talent_id, response_text)
        VALUES ($1, $2, $3)
        RETURNING {_APP_COLUMNS}
        """,
        internship_id,
        talent_id,
        response_text,
    )
    return InternshipApplication.from_row(row)


async def has_applied(conn: asyncpg.Connection, *, internship_id: str, talent_id: str) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM public.internship_applications WHERE internship_id = $1 AND talent_id = $2",
        internship_id,
        talent_id,
    )
    return row is not None


async def list_for_talent(conn: asyncpg.Connection, talent_id: str) -> list[InternshipApplication]:
    rows = await conn.fetch(
        f"SELECT {_APP_COLUMNS} FROM public.internship_applications WHERE talent_id = $1 ORDER BY submitted_at DESC",
        talent_id,
    )
    return [InternshipApplication.from_row(r) for r in rows]


async def list_for_internship(conn: asyncpg.Connection, internship_id: str) -> list[InternshipApplication]:
    rows = await conn.fetch(
        f"SELECT {_APP_COLUMNS} FROM public.internship_applications WHERE internship_id = $1 ORDER BY submitted_at ASC",
        internship_id,
    )
    return [InternshipApplication.from_row(r) for r in rows]


async def set_application_status(conn: asyncpg.Connection, application_id: str, status: str) -> InternshipApplication:
    row = await conn.fetchrow(
        f"""
        UPDATE public.internship_applications SET status = $2, reviewed_at = now()
        WHERE id = $1 RETURNING {_APP_COLUMNS}
        """,
        application_id,
        status,
    )
    return InternshipApplication.from_row(row)
