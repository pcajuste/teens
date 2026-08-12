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

from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.pool import get_pool
from app.repositories.campaign_reps_repository import auto_decline_expired_parent_approvals
from app.repositories.parent_records_repository import list_digest_enabled
from app.services.parent_service import send_digest_email
from app.services.resend_client import get_resend_client

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
