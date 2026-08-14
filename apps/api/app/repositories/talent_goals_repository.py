"""Data access for public.talent_goals (Build Prompt 5 deliverable 13:
Goal Setting and Progress Tracking).

Same shape convention as talent_profiles_repository.py: explicit
connection, frozen/slots dataclass with from_row.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import asyncpg

MAX_ACTIVE_GOALS = 3

_COLUMNS = "id, talent_id, goal_type, target_value, target_date, current_value, status, completed_at, created_at"

_DESCRIPTIONS: dict[str, str] = {
    "campaigns_completed": "Complete {n} campaigns",
    "earnings_total": "Earn ${n}",
    "categories_active": "Work in {n} categories",
    "badges_earned": "Earn {n} badges",
    "profile_completeness": "Reach {n}% profile completeness",
}


def describe_goal(goal_type: str, target_value: int) -> str:
    """Plain-language goal description shared by the goals-list UI copy
    and the "you hit your goal" completion email (Build Prompt 5/6
    deliverable 13/10) -- one place so the two surfaces can't drift."""
    template = _DESCRIPTIONS.get(goal_type, goal_type)
    n = target_value / 100 if goal_type == "earnings_total" else target_value
    return template.format(n=f"{n:.0f}" if goal_type != "earnings_total" else f"{n:.2f}")


@dataclass(frozen=True, slots=True)
class TalentGoal:
    id: str
    talent_id: str
    goal_type: str
    target_value: int
    target_date: date | None
    current_value: int
    status: str
    completed_at: datetime | None
    created_at: datetime

    @property
    def progress_percentage(self) -> int:
        if self.target_value <= 0:
            return 0
        return min(100, round((self.current_value / self.target_value) * 100))

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "TalentGoal":
        return cls(
            id=str(row["id"]),
            talent_id=str(row["talent_id"]),
            goal_type=row["goal_type"],
            target_value=row["target_value"],
            target_date=row["target_date"],
            current_value=row["current_value"],
            status=row["status"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
        )


async def count_active_goals(conn: asyncpg.Connection, talent_id: str) -> int:
    return await conn.fetchval(
        "SELECT COUNT(*) FROM public.talent_goals WHERE talent_id = $1 AND status = 'active'", talent_id
    )


async def create_goal(
    conn: asyncpg.Connection, talent_id: str, *, goal_type: str, target_value: int, target_date: date | None
) -> TalentGoal:
    """Caller (router) is responsible for the active-goal-count < 3 check
    up front so it can return a clean 409 with a specific message -- the
    migration's trg_enforce_max_active_goals trigger is a second,
    concurrency-safe backstop (two simultaneous requests both passing the
    app-level count check can't both land a 4th goal), not the primary
    enforcement path."""
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.talent_goals (talent_id, goal_type, target_value, target_date)
        VALUES ($1, $2, $3, $4)
        RETURNING {_COLUMNS}
        """,
        talent_id,
        goal_type,
        target_value,
        target_date,
    )
    return TalentGoal.from_row(row)


async def get_goal(conn: asyncpg.Connection, talent_id: str, goal_id: str) -> TalentGoal | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.talent_goals WHERE id = $1 AND talent_id = $2", goal_id, talent_id
    )
    return TalentGoal.from_row(row) if row else None


async def abandon_goal(conn: asyncpg.Connection, goal_id: str) -> TalentGoal | None:
    """Caller must already have fetched-and-validated the goal (ownership,
    not already 'completed') via get_goal -- this is a narrow status flip,
    matching campaign_talents_repository's convention of routers owning
    the state-machine legality check before calling a mutator."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.talent_goals SET status = 'abandoned' WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        goal_id,
    )
    return TalentGoal.from_row(row) if row else None


async def list_goals(conn: asyncpg.Connection, talent_id: str) -> list[TalentGoal]:
    """Active and completed goals only -- abandoned goals are excluded
    from the talent's own goals view (spec: "all active and recently
    completed goals"); there's no separate "abandoned goals history"
    surface in this build."""
    rows = await conn.fetch(
        f"""
        SELECT {_COLUMNS} FROM public.talent_goals
        WHERE talent_id = $1 AND status IN ('active', 'completed')
        ORDER BY created_at DESC
        """,
        talent_id,
    )
    return [TalentGoal.from_row(row) for row in rows]


async def current_metric_values(conn: asyncpg.Connection, talent_id: str) -> dict[str, int]:
    """One query per goal_type's source of truth. campaigns_completed and
    earnings_total intentionally mirror talent_profiles.brand_campaigns_completed
    / total_earnings_cents exactly (both already paid-status-based, see
    recompute_cached_totals's docstring) rather than a separate
    'confirmed' definition -- a goal progress bar reading differently
    from the dashboard's own completed-campaigns count for the same
    talent would be confusing, not more precise."""
    profile_row = await conn.fetchrow(
        "SELECT brand_campaigns_completed, total_earnings_cents, badges_earned_count, profile_completeness_score "
        "FROM public.talent_profiles WHERE id = $1",
        talent_id,
    )
    # campaigns.target_categories is an array (a campaign can target more
    # than one category) and campaign_talents has no single
    # "which category this talent actually worked in" column -- so this
    # counts distinct categories across every paid campaign's full
    # target_categories array, which can overcount a talent who completed
    # one multi-category campaign as active in several categories. Exact
    # per-talent category attribution would need a new column; flagged
    # rather than silently treated as precise.
    categories_active = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT cat) FROM (
            SELECT unnest(c.target_categories) AS cat
            FROM public.campaign_talents ct
            JOIN public.campaigns c ON c.id = ct.campaign_id
            WHERE ct.talent_id = $1 AND ct.status = 'paid'
        ) AS categories
        """,
        talent_id,
    )
    return {
        "campaigns_completed": profile_row["brand_campaigns_completed"],
        "earnings_total": profile_row["total_earnings_cents"],
        "badges_earned": profile_row["badges_earned_count"],
        "profile_completeness": profile_row["profile_completeness_score"],
        "categories_active": categories_active or 0,
    }


async def recompute_progress(conn: asyncpg.Connection, talent_id: str) -> list[TalentGoal]:
    """Updates current_value for every active goal from the live metric,
    marks status='completed' (+ completed_at) once current_value reaches
    target_value, and returns exactly the goals that completed *in this
    call* -- callers use that list to decide whether to send the
    "you hit your goal" email, so a goal that was already completed
    before this call must not appear twice."""
    active = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.talent_goals WHERE talent_id = $1 AND status = 'active'", talent_id
    )
    if not active:
        return []
    metrics = await current_metric_values(conn, talent_id)
    newly_completed: list[TalentGoal] = []
    for row in active:
        goal = TalentGoal.from_row(row)
        new_value = metrics.get(goal.goal_type, goal.current_value)
        if new_value == goal.current_value:
            continue
        if new_value >= goal.target_value:
            updated_row = await conn.fetchrow(
                f"""
                UPDATE public.talent_goals
                SET current_value = $2, status = 'completed', completed_at = now()
                WHERE id = $1 AND status = 'active'
                RETURNING {_COLUMNS}
                """,
                goal.id,
                new_value,
            )
            if updated_row is not None:
                newly_completed.append(TalentGoal.from_row(updated_row))
        else:
            await conn.execute("UPDATE public.talent_goals SET current_value = $2 WHERE id = $1", goal.id, new_value)
    return newly_completed
