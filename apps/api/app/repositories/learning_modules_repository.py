"""Data access for public.learning_modules and
public.rep_module_completions (Build Prompt 8H: Learning Modules and
Verified Badges).

The single most important rule enforced in this file: `correct_index`
within a quiz content block must never reach a client-facing response,
regardless of role -- including admin preview. That's implemented by
`strip_correct_index`, applied by `ModulePublicSerializer` (see
app/schemas/learning_modules.py), and by keeping the *only* function
that returns raw content_blocks (`get_module_with_answers`) named
distinctly and used only by the completion-scoring code path in
app/routers/learning_modules.py, which fetches it via a plain SELECT
(never exposed as a response body).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import asyncpg

# ══════════════════════════════════════════════════════════════════
# learning_modules
# ══════════════════════════════════════════════════════════════════

_MODULE_COLUMNS = """
    id, title, description, category, content_blocks, passing_score, badge_title,
    badge_description, badge_color, badge_icon, estimated_minutes, status,
    created_at, updated_at
"""


def strip_correct_index(content_blocks: list[dict]) -> list[dict]:
    """Returns a deep copy of content_blocks with every quiz question's
    correct_index field removed. This is the ONLY function in this
    codebase that is allowed to turn a raw content_blocks value into
    something safe to put in a response body -- every route that
    returns module content must route through this (directly or via
    ModulePublicSerializer)."""
    stripped: list[dict] = []
    for block in content_blocks:
        block_copy = dict(block)
        if block_copy.get("type") == "quiz":
            questions = block_copy.get("content") or []
            block_copy["content"] = [
                {k: v for k, v in q.items() if k != "correct_index"} for q in questions
            ]
        stripped.append(block_copy)
    return stripped


@dataclass(frozen=True, slots=True)
class LearningModule:
    id: str
    title: str
    description: str
    category: str | None
    content_blocks: list[dict]  # RAW -- includes correct_index. Never serialize directly.
    passing_score: int | None
    badge_title: str
    badge_description: str
    badge_color: str
    badge_icon: str | None
    estimated_minutes: int
    status: str
    created_at: datetime
    updated_at: datetime

    @property
    def public_content_blocks(self) -> list[dict]:
        return strip_correct_index(self.content_blocks)

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "LearningModule":
        return cls(
            id=str(row["id"]),
            title=row["title"],
            description=row["description"],
            category=row["category"],
            content_blocks=json.loads(row["content_blocks"]) if isinstance(row["content_blocks"], str) else row["content_blocks"],
            passing_score=row["passing_score"],
            badge_title=row["badge_title"],
            badge_description=row["badge_description"],
            badge_color=row["badge_color"],
            badge_icon=row["badge_icon"],
            estimated_minutes=row["estimated_minutes"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


async def create_module(
    conn: asyncpg.Connection,
    *,
    title: str,
    description: str,
    category: str | None,
    content_blocks: list[dict],
    passing_score: int | None,
    badge_title: str,
    badge_description: str,
    badge_color: str,
    badge_icon: str | None,
    estimated_minutes: int,
) -> LearningModule:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.learning_modules
            (title, description, category, content_blocks, passing_score, badge_title,
             badge_description, badge_color, badge_icon, estimated_minutes)
        VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10)
        RETURNING {_MODULE_COLUMNS}
        """,
        title,
        description,
        category,
        json.dumps(content_blocks),
        passing_score,
        badge_title,
        badge_description,
        badge_color,
        badge_icon,
        estimated_minutes,
    )
    return LearningModule.from_row(row)


async def get_by_id(conn: asyncpg.Connection, module_id: str) -> LearningModule | None:
    row = await conn.fetchrow(f"SELECT {_MODULE_COLUMNS} FROM public.learning_modules WHERE id = $1", module_id)
    return LearningModule.from_row(row) if row else None


async def list_all(conn: asyncpg.Connection) -> list[LearningModule]:
    rows = await conn.fetch(f"SELECT {_MODULE_COLUMNS} FROM public.learning_modules ORDER BY created_at DESC")
    return [LearningModule.from_row(r) for r in rows]


async def list_active(conn: asyncpg.Connection) -> list[LearningModule]:
    rows = await conn.fetch(f"SELECT {_MODULE_COLUMNS} FROM public.learning_modules WHERE status = 'active' ORDER BY created_at DESC")
    return [LearningModule.from_row(r) for r in rows]


async def update_module(
    conn: asyncpg.Connection,
    module_id: str,
    *,
    title: str,
    description: str,
    category: str | None,
    content_blocks: list[dict],
    passing_score: int | None,
    badge_title: str,
    badge_description: str,
    badge_color: str,
    badge_icon: str | None,
    estimated_minutes: int,
) -> LearningModule | None:
    """Legal only while status='draft' (spec: "Draft status only -- 409
    if active or archived")."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.learning_modules
        SET title = $2, description = $3, category = $4, content_blocks = $5::jsonb,
            passing_score = $6, badge_title = $7, badge_description = $8, badge_color = $9,
            badge_icon = $10, estimated_minutes = $11, updated_at = now()
        WHERE id = $1 AND status = 'draft'
        RETURNING {_MODULE_COLUMNS}
        """,
        module_id,
        title,
        description,
        category,
        json.dumps(content_blocks),
        passing_score,
        badge_title,
        badge_description,
        badge_color,
        badge_icon,
        estimated_minutes,
    )
    return LearningModule.from_row(row) if row else None


async def activate(conn: asyncpg.Connection, module_id: str) -> LearningModule | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.learning_modules SET status = 'active', updated_at = now()
        WHERE id = $1 AND status = 'draft'
        RETURNING {_MODULE_COLUMNS}
        """,
        module_id,
    )
    return LearningModule.from_row(row) if row else None


async def archive(conn: asyncpg.Connection, module_id: str) -> LearningModule | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.learning_modules SET status = 'archived', updated_at = now()
        WHERE id = $1 AND status = 'active'
        RETURNING {_MODULE_COLUMNS}
        """,
        module_id,
    )
    return LearningModule.from_row(row) if row else None


async def admin_module_stats(conn: asyncpg.Connection) -> dict[str, dict]:
    """Per-module completion_count/pass_rate/average_attempts/in_progress_count
    (spec deliverable 1's GET /admin/modules), keyed by module_id."""
    rows = await conn.fetch(
        """
        SELECT
            module_id,
            COUNT(*) FILTER (WHERE status = 'passed') AS passed_count,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed_count,
            COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress_count,
            AVG(attempts) AS average_attempts
        FROM public.rep_module_completions
        GROUP BY module_id
        """
    )
    stats: dict[str, dict] = {}
    for r in rows:
        passed = r["passed_count"]
        failed = r["failed_count"]
        denom = passed + failed
        stats[str(r["module_id"])] = {
            "completion_count": passed,
            "pass_rate": round(passed / denom, 2) if denom else None,
            "average_attempts": round(float(r["average_attempts"]), 2) if r["average_attempts"] is not None else None,
            "in_progress_count": r["in_progress_count"],
        }
    return stats


# ══════════════════════════════════════════════════════════════════
# rep_module_completions
# ══════════════════════════════════════════════════════════════════

_COMPLETION_COLUMNS = """
    id, rep_id, module_id, status, quiz_score, attempts, last_attempt_at, passed_at,
    badge_issued_at, disclosure_acknowledged_at, payout_cents, payout_status,
    stripe_transfer_id
"""


@dataclass(frozen=True, slots=True)
class RepModuleCompletion:
    id: str
    rep_id: str
    module_id: str
    status: str
    quiz_score: int | None
    attempts: int
    last_attempt_at: datetime | None
    passed_at: datetime | None
    badge_issued_at: datetime | None
    disclosure_acknowledged_at: datetime | None
    payout_cents: int | None
    payout_status: str | None
    stripe_transfer_id: str | None

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "RepModuleCompletion":
        return cls(
            id=str(row["id"]),
            rep_id=str(row["rep_id"]),
            module_id=str(row["module_id"]),
            status=row["status"],
            quiz_score=row["quiz_score"],
            attempts=row["attempts"],
            last_attempt_at=row["last_attempt_at"],
            passed_at=row["passed_at"],
            badge_issued_at=row["badge_issued_at"],
            disclosure_acknowledged_at=row["disclosure_acknowledged_at"],
            payout_cents=row["payout_cents"],
            payout_status=row["payout_status"],
            stripe_transfer_id=row["stripe_transfer_id"],
        )


async def get_for_rep_and_module(conn: asyncpg.Connection, rep_id: str, module_id: str) -> RepModuleCompletion | None:
    row = await conn.fetchrow(
        f"SELECT {_COMPLETION_COLUMNS} FROM public.rep_module_completions WHERE rep_id = $1 AND module_id = $2",
        rep_id,
        module_id,
    )
    return RepModuleCompletion.from_row(row) if row else None


async def list_for_rep(conn: asyncpg.Connection, rep_id: str) -> list[RepModuleCompletion]:
    rows = await conn.fetch(
        f"SELECT {_COMPLETION_COLUMNS} FROM public.rep_module_completions WHERE rep_id = $1",
        rep_id,
    )
    return [RepModuleCompletion.from_row(r) for r in rows]


async def has_passed(conn: asyncpg.Connection, rep_id: str, module_id: str) -> bool:
    """FTC gate check (spec deliverable 2) -- uses
    idx_rep_module_completions_ftc, which exists specifically to
    optimize this query on every campaign accept action."""
    row = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM public.rep_module_completions
            WHERE rep_id = $1 AND module_id = $2 AND status = 'passed'
        )
        """,
        rep_id,
        module_id,
    )
    return bool(row)


async def start_new(conn: asyncpg.Connection, *, rep_id: str, module_id: str, at: datetime) -> RepModuleCompletion:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.rep_module_completions
            (rep_id, module_id, status, attempts, last_attempt_at, disclosure_acknowledged_at)
        VALUES ($1, $2, 'in_progress', 1, $3, $3)
        RETURNING {_COMPLETION_COLUMNS}
        """,
        rep_id,
        module_id,
        at,
    )
    return RepModuleCompletion.from_row(row)


async def start_retake(conn: asyncpg.Connection, *, rep_id: str, module_id: str, at: datetime) -> RepModuleCompletion | None:
    """Legal only from status='failed' (spec deliverable 4: "If row
    exists with status 'failed': UPDATE status -> 'in_progress',
    increment attempts, set last_attempt_at = now()")."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.rep_module_completions
        SET status = 'in_progress', attempts = attempts + 1, last_attempt_at = $3,
            disclosure_acknowledged_at = $3
        WHERE rep_id = $1 AND module_id = $2 AND status = 'failed'
        RETURNING {_COMPLETION_COLUMNS}
        """,
        rep_id,
        module_id,
        at,
    )
    return RepModuleCompletion.from_row(row) if row else None


async def mark_passed(
    conn: asyncpg.Connection, completion_id: str, *, quiz_score: int | None, at: datetime
) -> RepModuleCompletion | None:
    """Legal only from status='in_progress'. Called inside the same
    transaction as the rep_profiles.badges append -- see
    app/routers/learning_modules.py's complete_module for the full
    atomic sequence."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.rep_module_completions
        SET status = 'passed', quiz_score = $2, passed_at = $3, badge_issued_at = $3
        WHERE id = $1 AND status = 'in_progress'
        RETURNING {_COMPLETION_COLUMNS}
        """,
        completion_id,
        quiz_score,
        at,
    )
    return RepModuleCompletion.from_row(row) if row else None


async def mark_failed(
    conn: asyncpg.Connection, completion_id: str, *, quiz_score: int | None, at: datetime
) -> RepModuleCompletion | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.rep_module_completions
        SET status = 'failed', quiz_score = $2, last_attempt_at = $3
        WHERE id = $1 AND status = 'in_progress'
        RETURNING {_COMPLETION_COLUMNS}
        """,
        completion_id,
        quiz_score,
        at,
    )
    return RepModuleCompletion.from_row(row) if row else None


# ══════════════════════════════════════════════════════════════════
# Admin analytics (spec deliverable 9, extending Prompt 13)
# ══════════════════════════════════════════════════════════════════


async def admin_analytics(conn: asyncpg.Connection, *, ftc_module_id: str | None) -> dict:
    module_totals = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total_modules,
            COUNT(*) FILTER (WHERE status = 'draft') AS draft_modules,
            COUNT(*) FILTER (WHERE status = 'active') AS active_modules,
            COUNT(*) FILTER (WHERE status = 'archived') AS archived_modules
        FROM public.learning_modules
        """
    )
    completion_totals = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress,
            COUNT(*) FILTER (WHERE status = 'passed') AS passed,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed
        FROM public.rep_module_completions
        """
    )
    per_module_rows = await conn.fetch(
        """
        SELECT
            m.id AS module_id, m.title, m.category,
            COUNT(c.id) FILTER (WHERE c.status = 'passed') AS passed_count,
            COUNT(c.id) FILTER (WHERE c.status = 'failed') AS failed_count,
            AVG(c.attempts) AS average_attempts
        FROM public.learning_modules m
        LEFT JOIN public.rep_module_completions c ON c.module_id = m.id
        GROUP BY m.id, m.title, m.category
        """
    )
    per_module: list[dict] = []
    for r in per_module_rows:
        passed = r["passed_count"]
        failed = r["failed_count"]
        denom = passed + failed
        per_module.append(
            {
                "module_id": str(r["module_id"]),
                "title": r["title"],
                "category": r["category"],
                "completion_count": passed,
                "pass_rate": round(passed / denom, 2) if denom else None,
                "average_attempts": round(float(r["average_attempts"]), 2) if r["average_attempts"] is not None else None,
            }
        )
    low_pass_rate = [m["module_id"] for m in per_module if m["pass_rate"] is not None and m["pass_rate"] < 0.5]
    high_attempts = [m["module_id"] for m in per_module if m["average_attempts"] is not None and m["average_attempts"] > 2]

    badge_distribution = await conn.fetch(
        """
        SELECT m.badge_title, m.category, COUNT(c.id) AS earned_count
        FROM public.rep_module_completions c
        JOIN public.learning_modules m ON m.id = c.module_id
        WHERE c.status = 'passed'
        GROUP BY m.badge_title, m.category
        ORDER BY earned_count DESC
        """
    )

    ftc_readiness = None
    if ftc_module_id:
        # Launch readiness metric: of reps who have ever attempted to
        # accept a campaign (i.e. have a campaign_reps row), what
        # percentage have passed the FTC module?
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT cr.rep_id) AS attempted_reps,
                COUNT(DISTINCT cr.rep_id) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM public.rep_module_completions rmc
                        WHERE rmc.rep_id = cr.rep_id AND rmc.module_id = $1 AND rmc.status = 'passed'
                    )
                ) AS passed_reps
            FROM public.campaign_reps cr
            """,
            ftc_module_id,
        )
        attempted = row["attempted_reps"]
        ftc_readiness = {
            "attempted_reps": attempted,
            "passed_reps": row["passed_reps"],
            "pass_percentage": round(row["passed_reps"] / attempted * 100, 1) if attempted else None,
        }

    return {
        "total_modules": module_totals["total_modules"],
        "draft_modules": module_totals["draft_modules"],
        "active_modules": module_totals["active_modules"],
        "archived_modules": module_totals["archived_modules"],
        "completions_in_progress": completion_totals["in_progress"],
        "completions_passed": completion_totals["passed"],
        "completions_failed": completion_totals["failed"],
        "per_module": per_module,
        "modules_flagged_low_pass_rate": low_pass_rate,
        "modules_flagged_high_attempts": high_attempts,
        "badge_distribution": [
            {"badge_title": r["badge_title"], "category": r["category"], "earned_count": r["earned_count"]}
            for r in badge_distribution
        ],
        "ftc_module_readiness": ftc_readiness,
    }


# ══════════════════════════════════════════════════════════════════
# Parent dashboard addition (spec deliverable 8)
# ══════════════════════════════════════════════════════════════════


async def parent_dashboard_activity(conn: asyncpg.Connection, rep_id: str, *, ftc_module_id: str | None) -> dict:
    """GET /parent/dashboard's module_activity block. Parents never see
    quiz_score or which questions were answered incorrectly -- only
    completion status and badges earned (spec: "the outcome, not the
    struggle")."""
    totals = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total_started,
            COUNT(*) FILTER (WHERE status = 'passed') AS total_passed,
            COUNT(*) FILTER (WHERE status = 'failed') AS total_failed
        FROM public.rep_module_completions
        WHERE rep_id = $1
        """,
        rep_id,
    )
    badges_row = await conn.fetchrow("SELECT badges FROM public.rep_profiles WHERE id = $1", rep_id)
    badges_raw = badges_row["badges"] if badges_row else "[]"
    badges = json.loads(badges_raw) if isinstance(badges_raw, str) else (badges_raw or [])
    badges_earned = [{"badge_title": b["badge_title"], "earned_at": b["earned_at"]} for b in badges]

    ftc_passed = False
    if ftc_module_id:
        ftc_passed = await has_passed(conn, rep_id, ftc_module_id)

    return {
        "total_started": totals["total_started"],
        "total_passed": totals["total_passed"],
        "total_failed": totals["total_failed"],
        "badges_earned": badges_earned,
        "ftc_module_passed": ftc_passed,
    }
