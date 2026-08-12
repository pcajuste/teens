"""Scheduled-job runner.

Mechanism chosen: **Railway cron** hitting `POST
/internal/jobs/run/{job_name}` on a schedule, authenticated via the
`X-Jobs-Runner-Secret` header (JOBS_RUNNER_SECRET). Chosen over a
Supabase Edge Function because job bodies (parent digests, invite
expiry, campaign-approval timeouts — Prompt 3/4A/5) need the same
service-layer code (parent_service, email_service) that the FastAPI
app already imports; an Edge Function would either duplicate that
logic in Deno/TypeScript or call back into the API anyway, so calling
the API directly from a Railway cron trigger is one less moving part.

Jobs register themselves in JOB_REGISTRY by name. Prompt 3 registers
one no-op job end-to-end to prove the schedule fires; Prompt 4A adds
the monthly parent-digest job. The invite-expiry / parent-approval
48-hour timeout job is Prompt 5's responsibility (it needs
rep_profiles/campaign matching that doesn't exist yet).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Final

from fastapi import APIRouter, Header, HTTPException, status

from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.db.pool import get_pool
from app.repositories import campaign_milestones_repository, campaign_reps_repository, exclusivity_repository
from app.repositories.campaign_reps_repository import auto_decline_expired_parent_approvals
from app.repositories.intelligence_repository import insert_events, list_pending_events, mark_written
from app.repositories.parent_records_repository import list_digest_enabled
from app.services import payout_service
from app.services.intelligence_service import anonymize
from app.services.parent_service import send_digest_email
from app.services.resend_client import get_resend_client

import logging

_logger = logging.getLogger("teenure.jobs.milestone_auto_release")

MILESTONE_AUTO_RELEASE_WINDOW_HOURS = 24

JobFn = Callable[[], Awaitable[None]]

JOB_REGISTRY: Final[dict[str, JobFn]] = {}


def register_job(name: str) -> Callable[[JobFn], JobFn]:
    def _decorator(fn: JobFn) -> JobFn:
        JOB_REGISTRY[name] = fn
        return fn

    return _decorator


@register_job("noop_heartbeat")
async def noop_heartbeat() -> None:
    """Proves the scheduler → API → job-registry path works end-to-end.
    Does nothing else."""
    return None


@register_job("send_monthly_parent_digests")
async def send_monthly_parent_digests() -> None:
    """Runs monthly. One digest per parent_records row with
    digest_enabled=TRUE -- parent_service.send_digest_email builds the
    allow-listed content (Section 9A) and skips parents whose rep
    context can't be found."""
    settings = get_settings()
    resend_client = get_resend_client(settings)
    pool = get_pool()
    async with pool.acquire() as conn:
        parents = await list_digest_enabled(conn)
        for parent in parents:
            await send_digest_email(conn, resend_client, parent_id=parent.parent_id)


@register_job("auto_decline_expired_parent_approvals")
async def auto_decline_expired_parent_approvals_job() -> None:
    """Runs frequently (e.g. every 15 minutes via Railway cron). Build
    Prompt 5 deliverable 7: enforces the 48-hour parent-approval window
    on campaign invitations -- any campaign_reps row still
    status='invited'/parent_approval_status='pending' past its
    parent_approval_deadline is auto-declined so a non-response doesn't
    leave an invitation open indefinitely. The DB update itself lives in
    campaign_reps_repository.auto_decline_expired_parent_approvals so it
    can be unit-tested directly against a real connection without
    waiting on a real clock (Build Prompt 5 acceptance criterion)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await auto_decline_expired_parent_approvals(conn, now=datetime.now(timezone.utc))


@register_job("write_intelligence_events")
async def write_intelligence_events_job() -> None:
    """Runs frequently (e.g. every 15 minutes via Railway cron), same
    cadence as auto_decline_expired_parent_approvals_job above. Build
    Prompt 14 deliverable 2: fires whenever a campaign_reps row has
    reached 'confirmed' or 'paid'. The runner is poll-based (Prompt 3
    has no per-row DB trigger into the API), so "fires when a row
    transitions" is implemented as "processes every such row that
    hasn't been processed yet" -- intelligence_repository.list_pending_events
    filters on campaign_reps.intelligence_event_written_at IS NULL,
    which this job sets once its rows are written, so each transition
    is anonymized exactly once. app/services/intelligence_service.anonymize
    does the actual PII-stripping/bucketing; this job only wires the
    read -> anonymize -> write -> mark-done pipeline together."""
    pool = get_pool()
    async with pool.acquire() as conn:
        pending = await list_pending_events(conn)
        if not pending:
            return
        events = [event for source in pending for event in anonymize(source)]
        await insert_events(conn, events)
        await mark_written(conn, [source.campaign_rep_id for source in pending], at=datetime.now(timezone.utc))


@register_job("milestone_auto_release")
async def milestone_auto_release_job() -> None:
    """Runs every 30 minutes (Build Prompt 8B deliverable 6). Finds
    campaign_rep_milestones rows with verification_method='rep_submission',
    status='submitted', submitted_at older than the 24h review window,
    and dispute_flag=false, then releases payout for each via
    payout_service.release_milestone_payout and advances the row to
    'confirmed' -- the same confirm-then-release sequencing
    POST .../milestones/:milestone_id/confirm uses for the
    brand-initiated path, just triggered by the clock instead of a
    brand click. Idempotent by construction: release_milestone_payout
    is a no-op ("already_processed") for a row that already has a
    stripe_transfer_id, and campaign_milestones_repository.confirm's own
    WHERE status = 'submitted' guard means a row already moved past
    'submitted' (by a second run, or a brand's own manual confirm
    racing this job) is simply skipped rather than double-confirmed.
    Every release is logged for admin audit (acceptance criterion)."""
    settings = get_settings()
    pool = get_pool()
    older_than = datetime.now(timezone.utc) - timedelta(hours=MILESTONE_AUTO_RELEASE_WINDOW_HOURS)
    async with pool.acquire() as conn:
        eligible = await campaign_milestones_repository.list_eligible_for_auto_release(conn, older_than=older_than)
        for crm in eligible:
            payout_cents = await campaign_milestones_repository.compute_payout_cents(conn, crm.id)
            confirmed = await campaign_milestones_repository.confirm(
                conn, crm.id, payout_cents=payout_cents or 0, at=datetime.now(timezone.utc)
            )
            if confirmed is None:
                # Already moved past 'submitted' since list_eligible_for_auto_release
                # was read -- a second run of this job, or a brand's
                # manual confirm/dispute, got there first.
                continue
            result = await payout_service.release_milestone_payout(conn, settings, crm.id)
            agg = await campaign_milestones_repository.bump_campaign_rep_milestone_totals(conn, confirmed.campaign_rep_id)
            if agg["completed_count"] >= agg["total_milestones"]:
                await campaign_reps_repository.mark_confirmed_via_final_milestone(
                    conn, confirmed.campaign_rep_id, at=datetime.now(timezone.utc)
                )
            _logger.info(
                "milestone_auto_release: campaign_rep_milestone_id=%s outcome=%s stripe_transfer_id=%s",
                crm.id,
                result.outcome,
                result.stripe_transfer_id,
            )


@register_job("exclusivity_auto_expire")
async def exclusivity_auto_expire_job() -> None:
    """Runs hourly (Build Prompt 8C deliverable 6, external scheduler
    assumption -- only the job body is implemented here, following
    milestone_auto_release_job's exact pattern above). Finds
    category_exclusivity_agreements with ends_at < now() and
    status = 'active', sets status = 'expired'. Idempotent by
    construction: exclusivity_repository.expire_due's own
    WHERE status = 'active' guard means a row already expired by an
    earlier run of this job simply doesn't match a second time, so
    running the job twice against the same agreement logs exactly once.
    Does NOT initiate refunds -- expiry is the natural, no-refund end of
    an agreement (admin cancellation, not expiry, is the only refund
    path -- see app/routers/admin.py's cancel_exclusivity_agreement)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        expired = await exclusivity_repository.expire_due(conn, now=datetime.now(timezone.utc))
        for agreement in expired:
            _logger.info(
                "exclusivity_auto_expire: agreement_id=%s brand_id=%s category=%s city=%s ends_at=%s",
                agreement.id,
                agreement.brand_id,
                agreement.category,
                agreement.city,
                agreement.ends_at,
            )


router = APIRouter(prefix="/internal/jobs", tags=["jobs"])


@router.post("/run/{job_name}")
async def run_job(job_name: str, x_jobs_runner_secret: str | None = Header(default=None)) -> dict:
    settings = get_settings()
    if x_jobs_runner_secret != settings.jobs_runner_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_jobs_runner_secret", "message": "Missing or invalid runner secret."},
        )

    job = JOB_REGISTRY.get(job_name)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "unknown_job", "message": f"No job registered as '{job_name}'."},
        )

    await job()
    return {"job": job_name, "status": "ok"}
