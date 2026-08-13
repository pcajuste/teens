"""Parent-portal service. Prompt 4A.

Every function here respects the parent-facing data minimization
boundary (Section 9A): no recruiter message content, no submission
text/files, no brand contact details ever cross into a parent-facing
send or record.

Signatures take an explicit `conn`/`resend_client` rather than
constructing their own -- these are called both from request-scoped
routers (app/routers/parent.py) and from the standalone monthly-digest
job (app/jobs/runner.py), which has no request to hang a Depends chain
off of. record_campaign_approval/record_campaign_block operate on
(talent_id, campaign_id) rather than Prompt 3's originally-stubbed
campaign_talent_id -- that's what the actual routes
(POST /parent/campaigns/:campaign_id/approve) have on hand.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import asyncpg

from app.repositories import campaign_talents_repository, parent_records_repository
from app.services.email_service import (
    send_campaign_blocked_notice_to_rep,
    send_digest_email as _send_digest_email_via_client,
)
from app.services.resend_client import ResendClient

# 48h window a parent has to approve/block a pending campaign
# invitation, shared by both entry points that create a campaign_talents
# row (talent self-apply in app/routers/talents.py, brand-initiated invite in
# app/routers/brands.py) -- previously duplicated as a module constant
# in talents.py alone; centralized here since determine_parent_approval
# below is now the single place that computes it.
PARENT_APPROVAL_WINDOW_HOURS = 48


async def determine_parent_approval(conn: asyncpg.Connection, talent_id: str) -> tuple[str, datetime | None]:
    """Whether a new campaign_talents row for this talent needs parent
    approval, and its deadline if so. Single source of truth for both
    the talent self-apply path and the brand-invite path -- both create a
    campaign_talents row identically from this point on (Build Prompt 8's
    invite endpoint reuses this rather than re-deriving the same
    decision a second way, which is exactly how Prompt 5's
    auto_decline_expired_parent_approvals ended up with two
    silently-diverging copies -- see that function's docstring)."""
    parent = await parent_records_repository.get_parent_by_talent_id(conn, talent_id)
    if parent is not None and parent.campaign_approval_required:
        deadline = datetime.now(timezone.utc) + timedelta(hours=PARENT_APPROVAL_WINDOW_HOURS)
        return "pending", deadline
    return "not_required", None


async def send_campaign_approval_request(
    conn: asyncpg.Connection, resend_client: ResendClient, *, talent_id: str, campaign_id: str
) -> None:
    """Notify a parent that a campaign is awaiting their approval.
    Called by Prompt 5 when a talent with campaign_approval_required=TRUE
    is invited/matched to a campaign."""
    parent = await parent_records_repository.get_parent_by_talent_id(conn, talent_id)
    if parent is None:
        return
    brief = await campaign_talents_repository.get_brief_for_talent_and_campaign(conn, talent_id, campaign_id)
    if brief is None:
        return
    from app.services.email_service import send_campaign_approval_request_email

    await send_campaign_approval_request_email(parent.parent_email, brief, resend_client)


async def record_campaign_approval(conn: asyncpg.Connection, *, talent_id: str, campaign_id: str) -> bool:
    """Idempotent: returns True if the invitation is now (or already
    was) approved, False if no matching pending/approved row exists."""
    status = await campaign_talents_repository.get_campaign_talent_approval_status(conn, talent_id, campaign_id)
    if status is None:
        return False
    if status == "approved":
        return True
    if status != "pending":
        return False
    await campaign_talents_repository.approve_campaign(conn, talent_id, campaign_id, decided_at=datetime.now(timezone.utc))
    return True


async def record_campaign_block(
    conn: asyncpg.Connection, resend_client: ResendClient, *, talent_id: str, campaign_id: str
) -> bool:
    status = await campaign_talents_repository.get_campaign_talent_approval_status(conn, talent_id, campaign_id)
    if status is None:
        return False
    await campaign_talents_repository.block_campaign(conn, talent_id, campaign_id, decided_at=datetime.now(timezone.utc))

    talent = await parent_records_repository.get_talent_context(conn, talent_id)
    if talent is not None:
        await send_campaign_blocked_notice_to_rep(talent.talent_email, resend_client)
    return True


async def apply_values_filter(conn: asyncpg.Connection, *, talent_id: str, campaign_category: str) -> bool:
    """True if `campaign_category` is allowed for `talent_id`. Enforced
    server-side in GET /talents/campaigns/available (Prompt 5) -- the talent
    never sees a blocked-category campaign as an option."""
    parent = await parent_records_repository.get_parent_by_talent_id(conn, talent_id)
    if parent is None:
        return True
    return campaign_category not in parent.values_filters


async def send_digest_email(conn: asyncpg.Connection, resend_client: ResendClient, *, parent_id: str) -> None:
    """Compose and send one parent's monthly digest. Content is
    allow-listed to campaigns completed this month, earnings this
    month and lifetime, profile-completeness change, and active
    categories -- never recruiter messages, submissions, or brand
    contact details (Section 9A)."""
    parent = await parent_records_repository.get_parent_by_id(conn, parent_id)
    if parent is None or not parent.digest_enabled:
        return

    talent = await parent_records_repository.get_talent_context(conn, parent.talent_id)
    if talent is None:
        return

    since = parent.digest_last_sent_at or datetime(1970, 1, 1, tzinfo=timezone.utc)
    stats = await campaign_talents_repository.monthly_digest_stats(conn, parent.talent_id, since=since)

    previous_score = parent.last_digest_profile_completeness_score
    completeness_change = None if previous_score is None else talent.profile_completeness_score - previous_score

    await _send_digest_email_via_client(
        parent.parent_email,
        resend_client,
        talent_display_name=talent.display_name,
        campaigns_completed_this_month=stats["campaigns_completed_this_month"],
        earnings_this_month_cents=stats["earnings_this_month_cents"],
        lifetime_earnings_cents=talent.total_earnings_cents,
        profile_completeness_score=talent.profile_completeness_score,
        profile_completeness_change=completeness_change,
        active_categories=stats["active_categories"],
    )

    now = datetime.now(timezone.utc)
    await parent_records_repository.update_digest_snapshot(
        conn, parent_id, sent_at=now, score=talent.profile_completeness_score
    )
