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
the monthly parent-digest job and the invite-expiry job onto this same
registry.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Final

from fastapi import APIRouter, Header, HTTPException, status

from app.core.config import get_settings

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
