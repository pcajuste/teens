"""Internal routes not part of the public API surface (Section 8 [PUBLIC]
exclusions don't apply here — these aren't reachable by end users at all,
only by the Railway cron scheduler presenting JOBS_RUNNER_SECRET).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings
from app.jobs.runner import run_job

router = APIRouter(prefix="/internal", tags=["internal"])


def verify_jobs_runner_secret(
    x_jobs_runner_secret: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if x_jobs_runner_secret != settings.jobs_runner_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid runner secret")


@router.post("/jobs/run/{job_name}", dependencies=[Depends(verify_jobs_runner_secret)])
def run_scheduled_job(job_name: str) -> dict:
    try:
        return run_job(job_name)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
