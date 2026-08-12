"""Data access for public.challenges and public.challenge_submissions
(Build Prompt 8G: Skill Challenges).

Two distinct dataclasses represent a submission row, on purpose:
`ChallengeSubmission` (brand/admin-facing, includes brand_note) and
`RepChallengeSubmission` (rep/parent-facing, has no field for
brand_note at all). This is the "explicit serializer exclusion, not
just RLS trust" the spec calls for -- brand_note simply cannot leak
through a rep-facing code path since there is no attribute to read it
from, independent of whatever RLS policy is (or isn't) in force for a
given connection.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

# ══════════════════════════════════════════════════════════════════
# challenges
# ══════════════════════════════════════════════════════════════════

_CHALLENGE_COLUMNS = """
    id, brand_id, title, brief, category, target_cities, submission_format,
    submission_prompt, status, max_submissions, submissions_count, opens_at,
    closes_at, conversion_count, created_at, updated_at
"""


@dataclass(frozen=True, slots=True)
class Challenge:
    id: str
    brand_id: str
    title: str
    brief: str
    category: str
    target_cities: list[str]
    submission_format: str
    submission_prompt: str
    status: str
    max_submissions: int | None
    submissions_count: int
    opens_at: datetime | None
    closes_at: datetime | None
    conversion_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "Challenge":
        return cls(
            id=str(row["id"]),
            brand_id=str(row["brand_id"]),
            title=row["title"],
            brief=row["brief"],
            category=row["category"],
            target_cities=list(row["target_cities"] or []),
            submission_format=row["submission_format"],
            submission_prompt=row["submission_prompt"],
            status=row["status"],
            max_submissions=row["max_submissions"],
            submissions_count=row["submissions_count"],
            opens_at=row["opens_at"],
            closes_at=row["closes_at"],
            conversion_count=row["conversion_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


async def create_challenge(
    conn: asyncpg.Connection,
    *,
    brand_id: str,
    title: str,
    brief: str,
    category: str,
    target_cities: list[str],
    submission_format: str,
    submission_prompt: str,
    max_submissions: int | None,
    opens_at: datetime | None,
    closes_at: datetime | None,
) -> Challenge:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.challenges
            (brand_id, title, brief, category, target_cities, submission_format,
             submission_prompt, max_submissions, opens_at, closes_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING {_CHALLENGE_COLUMNS}
        """,
        brand_id,
        title,
        brief,
        category,
        target_cities,
        submission_format,
        submission_prompt,
        max_submissions,
        opens_at,
        closes_at,
    )
    return Challenge.from_row(row)


async def get_by_id(conn: asyncpg.Connection, challenge_id: str) -> Challenge | None:
    row = await conn.fetchrow(f"SELECT {_CHALLENGE_COLUMNS} FROM public.challenges WHERE id = $1", challenge_id)
    return Challenge.from_row(row) if row else None


async def get_by_id_and_brand(conn: asyncpg.Connection, challenge_id: str, brand_id: str) -> Challenge | None:
    row = await conn.fetchrow(
        f"SELECT {_CHALLENGE_COLUMNS} FROM public.challenges WHERE id = $1 AND brand_id = $2", challenge_id, brand_id
    )
    return Challenge.from_row(row) if row else None


async def list_for_brand(conn: asyncpg.Connection, brand_id: str) -> list[Challenge]:
    rows = await conn.fetch(
        f"SELECT {_CHALLENGE_COLUMNS} FROM public.challenges WHERE brand_id = $1 ORDER BY created_at DESC", brand_id
    )
    return [Challenge.from_row(r) for r in rows]


async def update_challenge(
    conn: asyncpg.Connection,
    challenge_id: str,
    brand_id: str,
    *,
    title: str,
    brief: str,
    category: str,
    target_cities: list[str],
    submission_format: str,
    submission_prompt: str,
    max_submissions: int | None,
    opens_at: datetime | None,
    closes_at: datetime | None,
) -> Challenge | None:
    """Legal only while status='draft' (spec: "Legal only in 'draft'
    status -- return 409 if status is 'active' or 'closed'")."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.challenges
        SET title = $3, brief = $4, category = $5, target_cities = $6, submission_format = $7,
            submission_prompt = $8, max_submissions = $9, opens_at = $10, closes_at = $11, updated_at = now()
        WHERE id = $1 AND brand_id = $2 AND status = 'draft'
        RETURNING {_CHALLENGE_COLUMNS}
        """,
        challenge_id,
        brand_id,
        title,
        brief,
        category,
        target_cities,
        submission_format,
        submission_prompt,
        max_submissions,
        opens_at,
        closes_at,
    )
    return Challenge.from_row(row) if row else None


async def activate(conn: asyncpg.Connection, challenge_id: str, brand_id: str, *, opens_at: datetime) -> Challenge | None:
    """Legal only from 'draft'. opens_at is only set here if the row's
    own opens_at is still NULL (spec: "Sets opens_at to now() if not
    specified") -- a brand-specified future opens_at is preserved."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.challenges
        SET status = 'active', opens_at = COALESCE(opens_at, $3), updated_at = now()
        WHERE id = $1 AND brand_id = $2 AND status = 'draft'
        RETURNING {_CHALLENGE_COLUMNS}
        """,
        challenge_id,
        brand_id,
        opens_at,
    )
    return Challenge.from_row(row) if row else None


async def close(conn: asyncpg.Connection, challenge_id: str, brand_id: str) -> Challenge | None:
    """Legal only from 'active'. Idempotent at the router layer: a
    challenge already 'closed' simply doesn't match this WHERE clause,
    so the router re-fetches and returns 200 with current state rather
    than treating a None result here as an error (spec: "closing an
    already-closed challenge returns the current state with a 200, not
    a 409")."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.challenges SET status = 'closed', updated_at = now()
        WHERE id = $1 AND brand_id = $2 AND status = 'active'
        RETURNING {_CHALLENGE_COLUMNS}
        """,
        challenge_id,
        brand_id,
    )
    return Challenge.from_row(row) if row else None


async def increment_submissions_count(conn: asyncpg.Connection, challenge_id: str) -> None:
    await conn.execute(
        "UPDATE public.challenges SET submissions_count = submissions_count + 1, updated_at = now() WHERE id = $1",
        challenge_id,
    )


async def increment_conversion_count(conn: asyncpg.Connection, challenge_id: str) -> None:
    await conn.execute(
        "UPDATE public.challenges SET conversion_count = conversion_count + 1, updated_at = now() WHERE id = $1",
        challenge_id,
    )


async def list_available_for_rep(
    conn: asyncpg.Connection, *, rep_id: str, categories: list[str], city: str
) -> list[Challenge]:
    """GET /reps/challenges/available matching (spec deliverable 4):
    active, category overlap, city match-or-global, not already
    submitted, not full. Mirrors campaigns_repository.list_available_for_rep's
    shape exactly (same matching semantics, different table) -- no
    parent values_filter applied here (challenges are unpaid, no
    parent-approval gate; see the router's own docstring for the
    documented decision)."""
    rows = await conn.fetch(
        f"""
        SELECT {_CHALLENGE_COLUMNS} FROM public.challenges c
        WHERE c.status = 'active'
          AND c.category = ANY($2::text[])
          AND (
                array_length(c.target_cities, 1) IS NULL
                OR $3 = ANY (c.target_cities)
              )
          AND (c.max_submissions IS NULL OR c.submissions_count < c.max_submissions)
          AND NOT EXISTS (
                SELECT 1 FROM public.challenge_submissions cs
                WHERE cs.challenge_id = c.id AND cs.rep_id = $1
              )
        ORDER BY c.created_at DESC
        """,
        rep_id,
        categories,
        city,
    )
    return [Challenge.from_row(r) for r in rows]


async def auto_close_due(conn: asyncpg.Connection, *, now: datetime) -> list[Challenge]:
    """challenge_auto_close job (Build Prompt 8G deliverable 7): closes
    every active challenge whose closes_at has passed. Idempotent by
    construction -- the WHERE status = 'active' guard means a challenge
    already closed by an earlier run of this job (or a brand's own
    manual close) simply doesn't match a second time."""
    rows = await conn.fetch(
        f"""
        UPDATE public.challenges SET status = 'closed', updated_at = now()
        WHERE status = 'active' AND closes_at IS NOT NULL AND closes_at < $1
        RETURNING {_CHALLENGE_COLUMNS}
        """,
        now,
    )
    return [Challenge.from_row(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
# challenge_submissions -- brand/admin-facing (includes brand_note)
# ══════════════════════════════════════════════════════════════════

_SUBMISSION_COLUMNS = """
    id, challenge_id, rep_id, submission_text, submission_file_urls, status, brand_note,
    converted_to_campaign_id, payout_cents, payout_status, stripe_transfer_id,
    submitted_at, reviewed_at, converted_at, paid_at
"""


@dataclass(frozen=True, slots=True)
class ChallengeSubmission:
    id: str
    challenge_id: str
    rep_id: str
    submission_text: str | None
    submission_file_urls: list[str]
    status: str
    brand_note: str | None
    converted_to_campaign_id: str | None
    payout_cents: int | None
    payout_status: str | None
    stripe_transfer_id: str | None
    submitted_at: datetime
    reviewed_at: datetime | None
    converted_at: datetime | None
    paid_at: datetime | None

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "ChallengeSubmission":
        return cls(
            id=str(row["id"]),
            challenge_id=str(row["challenge_id"]),
            rep_id=str(row["rep_id"]),
            submission_text=row["submission_text"],
            submission_file_urls=list(row["submission_file_urls"] or []),
            status=row["status"],
            brand_note=row["brand_note"],
            converted_to_campaign_id=str(row["converted_to_campaign_id"]) if row["converted_to_campaign_id"] else None,
            payout_cents=row["payout_cents"],
            payout_status=row["payout_status"],
            stripe_transfer_id=row["stripe_transfer_id"],
            submitted_at=row["submitted_at"],
            reviewed_at=row["reviewed_at"],
            converted_at=row["converted_at"],
            paid_at=row["paid_at"],
        )


async def create_submission(
    conn: asyncpg.Connection,
    *,
    challenge_id: str,
    rep_id: str,
    submission_text: str | None,
    submission_file_urls: list[str],
) -> ChallengeSubmission:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.challenge_submissions (challenge_id, rep_id, submission_text, submission_file_urls)
        VALUES ($1, $2, $3, $4)
        RETURNING {_SUBMISSION_COLUMNS}
        """,
        challenge_id,
        rep_id,
        submission_text,
        submission_file_urls,
    )
    return ChallengeSubmission.from_row(row)


async def get_submission_by_id(conn: asyncpg.Connection, submission_id: str) -> ChallengeSubmission | None:
    """Named distinctly from Challenge's own get_by_id above -- two
    same-named module-level functions would silently shadow each other
    (the second definition wins), which is exactly the bug this naming
    avoids."""
    row = await conn.fetchrow(f"SELECT {_SUBMISSION_COLUMNS} FROM public.challenge_submissions WHERE id = $1", submission_id)
    return ChallengeSubmission.from_row(row) if row else None


async def get_by_id_and_challenge(conn: asyncpg.Connection, submission_id: str, challenge_id: str) -> ChallengeSubmission | None:
    row = await conn.fetchrow(
        f"SELECT {_SUBMISSION_COLUMNS} FROM public.challenge_submissions WHERE id = $1 AND challenge_id = $2",
        submission_id,
        challenge_id,
    )
    return ChallengeSubmission.from_row(row) if row else None


async def get_for_rep_and_challenge(conn: asyncpg.Connection, rep_id: str, challenge_id: str) -> ChallengeSubmission | None:
    row = await conn.fetchrow(
        f"SELECT {_SUBMISSION_COLUMNS} FROM public.challenge_submissions WHERE rep_id = $1 AND challenge_id = $2",
        rep_id,
        challenge_id,
    )
    return ChallengeSubmission.from_row(row) if row else None


async def get_by_stripe_transfer_id(conn: asyncpg.Connection, stripe_transfer_id: str) -> ChallengeSubmission | None:
    row = await conn.fetchrow(
        f"SELECT {_SUBMISSION_COLUMNS} FROM public.challenge_submissions WHERE stripe_transfer_id = $1", stripe_transfer_id
    )
    return ChallengeSubmission.from_row(row) if row else None


async def list_for_challenge(conn: asyncpg.Connection, challenge_id: str) -> list[ChallengeSubmission]:
    rows = await conn.fetch(
        f"SELECT {_SUBMISSION_COLUMNS} FROM public.challenge_submissions WHERE challenge_id = $1 ORDER BY submitted_at DESC",
        challenge_id,
    )
    return [ChallengeSubmission.from_row(r) for r in rows]


async def list_for_rep(conn: asyncpg.Connection, rep_id: str) -> list[ChallengeSubmission]:
    """Rep's own submission history -- router filters/remaps status for
    the rep-facing response (declined excluded, reviewed shown as
    submitted -- spec deliverable 4)."""
    rows = await conn.fetch(
        f"SELECT {_SUBMISSION_COLUMNS} FROM public.challenge_submissions WHERE rep_id = $1 ORDER BY submitted_at DESC",
        rep_id,
    )
    return [ChallengeSubmission.from_row(r) for r in rows]


async def mark_reviewed(conn: asyncpg.Connection, submission_id: str, *, brand_note: str | None, at: datetime) -> ChallengeSubmission | None:
    """Legal only from 'submitted'. Idempotent at the router layer the
    same way close() above is: the router treats an already-'reviewed'
    row as a success (re-fetch, 200), not this function's None result
    as an automatic 409 -- 'reviewed' is a brand-internal bookkeeping
    state, not a state machine a brand should get blocked re-entering."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.challenge_submissions
        SET status = 'reviewed', brand_note = COALESCE($2, brand_note), reviewed_at = $3
        WHERE id = $1 AND status = 'submitted'
        RETURNING {_SUBMISSION_COLUMNS}
        """,
        submission_id,
        brand_note,
        at,
    )
    return ChallengeSubmission.from_row(row) if row else None


async def mark_converted(
    conn: asyncpg.Connection,
    submission_id: str,
    *,
    converted_to_campaign_id: str,
    payout_cents: int,
    at: datetime,
) -> ChallengeSubmission | None:
    """Legal only from 'submitted' or 'reviewed' (spec 3b). Called
    inside the caller's transaction alongside the campaign_reps invite
    creation -- see app/routers/challenges.py's convert_submission for
    the full atomic sequence."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.challenge_submissions
        SET status = 'converted', converted_to_campaign_id = $2, payout_cents = $3,
            payout_status = 'pending', converted_at = $4
        WHERE id = $1 AND status IN ('submitted', 'reviewed')
        RETURNING {_SUBMISSION_COLUMNS}
        """,
        submission_id,
        converted_to_campaign_id,
        payout_cents,
        at,
    )
    return ChallengeSubmission.from_row(row) if row else None


async def mark_declined(conn: asyncpg.Connection, submission_id: str) -> ChallengeSubmission | None:
    """Legal only from 'submitted' or 'reviewed'. Idempotent at the
    router layer, same shape as close()/mark_reviewed() above."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.challenge_submissions SET status = 'declined'
        WHERE id = $1 AND status IN ('submitted', 'reviewed')
        RETURNING {_SUBMISSION_COLUMNS}
        """,
        submission_id,
    )
    return ChallengeSubmission.from_row(row) if row else None


async def set_payout_processing(conn: asyncpg.Connection, submission_id: str, *, stripe_transfer_id: str) -> ChallengeSubmission | None:
    """Legal only from payout_status='pending' -- same idempotency
    shape as campaign_reps_repository.set_payout_processing: a retried
    release_challenge_conversion_bonus call observes no matching row
    the second time and the caller treats that as 'already_processed'
    rather than a second Stripe Transfer."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.challenge_submissions
        SET payout_status = 'processing', stripe_transfer_id = $2
        WHERE id = $1 AND status = 'converted' AND payout_status = 'pending'
        RETURNING {_SUBMISSION_COLUMNS}
        """,
        submission_id,
        stripe_transfer_id,
    )
    return ChallengeSubmission.from_row(row) if row else None


async def set_payout_paid(conn: asyncpg.Connection, submission_id: str, *, at: datetime) -> ChallengeSubmission | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.challenge_submissions SET payout_status = 'paid', paid_at = $2
        WHERE id = $1 AND payout_status = 'processing'
        RETURNING {_SUBMISSION_COLUMNS}
        """,
        submission_id,
        at,
    )
    return ChallengeSubmission.from_row(row) if row else None


async def set_payout_failed(conn: asyncpg.Connection, submission_id: str) -> ChallengeSubmission | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.challenge_submissions SET payout_status = 'failed'
        WHERE id = $1 AND payout_status = 'processing'
        RETURNING {_SUBMISSION_COLUMNS}
        """,
        submission_id,
    )
    return ChallengeSubmission.from_row(row) if row else None


# ══════════════════════════════════════════════════════════════════
# No-PII rep card for a brand's challenge submissions inbox (spec
# deliverable 2's GET /brands/challenges/:id/submissions field list --
# "this is the no-PII card for challenge context").
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ChallengeSubmissionRepCard:
    rep_id: str
    display_name: str
    city: str
    categories: list[str]
    profile_completeness_score: int
    campaigns_completed: int
    average_rating: float | None
    challenges_converted_count: int
    challenge_conversion_rate: float | None


# ══════════════════════════════════════════════════════════════════
# Admin analytics (Build Prompt 8G deliverable 9, extending Prompt 13)
# ══════════════════════════════════════════════════════════════════

MIN_SUBMISSIONS_FOR_ZERO_CONVERSION_WARNING = 30


async def admin_analytics(conn: asyncpg.Connection) -> dict:
    totals = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total_challenges,
            COUNT(*) FILTER (WHERE status = 'active') AS active_challenges,
            COUNT(*) FILTER (WHERE status = 'closed') AS closed_challenges
        FROM public.challenges
        """
    )
    submission_totals = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total_submissions,
            COUNT(*) FILTER (WHERE status = 'converted') AS total_conversions,
            COALESCE(SUM(payout_cents) FILTER (WHERE payout_status = 'paid'), 0) AS bonus_total_paid_cents
        FROM public.challenge_submissions
        """
    )
    top_categories = await conn.fetch(
        """
        SELECT category, COUNT(cs.id) AS submissions_count
        FROM public.challenges c
        LEFT JOIN public.challenge_submissions cs ON cs.challenge_id = c.id
        GROUP BY category
        ORDER BY submissions_count DESC
        LIMIT 10
        """
    )
    brand_rows = await conn.fetch(
        """
        SELECT bp.id AS brand_id, bp.company_name,
               COALESCE(SUM(c.submissions_count), 0) AS submissions_count,
               COALESCE(SUM(c.conversion_count), 0) AS conversion_count
        FROM public.brand_profiles bp
        JOIN public.challenges c ON c.brand_id = bp.id
        GROUP BY bp.id, bp.company_name
        """
    )
    total_submissions = submission_totals["total_submissions"]
    total_conversions = submission_totals["total_conversions"]
    platform_conversion_rate = round(total_conversions / total_submissions, 2) if total_submissions else None

    brand_entries = [
        {
            "brand_id": str(r["brand_id"]),
            "company_name": r["company_name"],
            "submissions_count": r["submissions_count"],
            "conversion_count": r["conversion_count"],
            "conversion_rate": round(r["conversion_count"] / r["submissions_count"], 2) if r["submissions_count"] else None,
        }
        for r in brand_rows
    ]
    top_converting = sorted(
        [b for b in brand_entries if b["submissions_count"] > 0], key=lambda b: (b["conversion_rate"] or 0), reverse=True
    )[:10]
    zero_conversion = [
        b
        for b in brand_entries
        if b["conversion_count"] == 0 and b["submissions_count"] >= MIN_SUBMISSIONS_FOR_ZERO_CONVERSION_WARNING
    ]

    return {
        "total_challenges": totals["total_challenges"],
        "active_challenges": totals["active_challenges"],
        "closed_challenges": totals["closed_challenges"],
        "total_submissions": total_submissions,
        "platform_conversion_rate": platform_conversion_rate,
        "conversion_bonus_total_paid_cents": submission_totals["bonus_total_paid_cents"],
        "top_categories": [{"category": r["category"], "submissions_count": r["submissions_count"]} for r in top_categories],
        "top_converting_brands": top_converting,
        "zero_conversion_brands": zero_conversion,
    }


# ══════════════════════════════════════════════════════════════════
# Parent dashboard addition (Build Prompt 8G deliverable 10)
# ══════════════════════════════════════════════════════════════════


async def parent_dashboard_activity(conn: asyncpg.Connection, rep_id: str) -> dict:
    """GET /parent/dashboard's challenge_activity block. Declined
    submissions are excluded from both the totals and recent_submissions
    -- same protection extended to parents as to reps (spec deliverable
    10: "no reason to expose rejection to a parent who may pressure
    their child about it"). Converted submissions include the campaign
    the rep was invited to, since that's a financial event with a
    legitimate parental interest."""
    totals = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status != 'declined') AS total_submitted,
            COUNT(*) FILTER (WHERE status = 'converted') AS total_converted,
            COALESCE(SUM(payout_cents) FILTER (WHERE status = 'converted'), 0) AS total_bonus_earned_cents
        FROM public.challenge_submissions
        WHERE rep_id = $1
        """,
        rep_id,
    )
    recent = await conn.fetch(
        """
        SELECT cs.status, cs.submitted_at, cs.payout_cents, c.title AS challenge_title
        FROM public.challenge_submissions cs
        JOIN public.challenges c ON c.id = cs.challenge_id
        WHERE cs.rep_id = $1 AND cs.status != 'declined'
        ORDER BY cs.submitted_at DESC
        LIMIT 5
        """,
        rep_id,
    )
    return {
        "total_submitted": totals["total_submitted"],
        "total_converted": totals["total_converted"],
        "total_bonus_earned_cents": totals["total_bonus_earned_cents"],
        "recent_submissions": [
            {
                "challenge_title": r["challenge_title"],
                "submitted_at": r["submitted_at"],
                "status": "converted" if r["status"] == "converted" else "submitted",
                "bonus_earned_cents": r["payout_cents"] if r["status"] == "converted" else None,
            }
            for r in recent
        ],
    }


async def get_submission_rep_card(conn: asyncpg.Connection, rep_id: str) -> ChallengeSubmissionRepCard | None:
    row = await conn.fetchrow(
        """
        SELECT id, display_name, city, categories, profile_completeness_score,
               total_campaigns_completed, average_rating,
               challenges_submitted_count, challenges_converted_count
        FROM public.rep_profiles WHERE id = $1
        """,
        rep_id,
    )
    if row is None:
        return None
    submitted = row["challenges_submitted_count"]
    converted = row["challenges_converted_count"]
    rate = round(converted / submitted, 2) if submitted else None
    return ChallengeSubmissionRepCard(
        rep_id=str(row["id"]),
        display_name=row["display_name"],
        city=row["city"],
        categories=list(row["categories"] or []),
        profile_completeness_score=row["profile_completeness_score"],
        campaigns_completed=row["total_campaigns_completed"],
        average_rating=float(row["average_rating"]) if row["average_rating"] is not None else None,
        challenges_converted_count=converted,
        challenge_conversion_rate=rate,
    )
