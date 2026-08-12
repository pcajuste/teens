"""Scheduled-job runner (Prompt 3 scaffold).

Mechanism chosen: **Railway cron trigger** calling a single internal
HTTP endpoint, `POST /internal/jobs/run/{job_name}`, authenticated with
a shared secret (JOBS_RUNNER_SECRET) rather than a user JWT — cron has
no user session. Railway's own cron scheduler hits this route on a
fixed interval per job (see railway.json / service cron config added in
Prompt 17). Chosen over a Supabase Edge Function because the job logic
needs to reuse the same FastAPI app's DB session, settings, and service
modules (stripe/email/payout) rather than duplicating that setup in
Deno.

Jobs register themselves in JOB_REGISTRY by name. Prompt 5 registers
the invite-expiry sweep here; Prompt 14 registers the intelligence
aggregation job here. This prompt only wires up `noop`, proving the
registry + endpoint + auth actually work end-to-end.
"""

from __future__ import annotations

from typing import Callable

from app.core.config import get_settings
from app.core.db import get_connection
from app.services import parent_service, rep_service

JobFn = Callable[[], dict]


def noop() -> dict:
    """Trivial job proving the runner fires correctly. Does nothing."""
    return {"ran": "noop", "result": "ok"}


def expire_invites() -> dict:
    """Prompt 5: auto-decline 'invited' campaign_reps rows past their
    48-hour invite_expires_at. Extended by Prompt 4A (deliverable 9) to
    also auto-decline invitations whose parent_approval_deadline has
    lapsed without a parent decision -- both are 48h windows checked in
    the same sweep. Run on a short interval (e.g. every 15 minutes per
    Railway cron config) since the deadline is 48 hours, not something
    that needs sub-hour precision.
    """
    settings = get_settings()
    with get_connection(settings) as conn:
        expired_count = rep_service.expire_stale_invites(conn)
        parent_expired_count = rep_service.expire_lapsed_parent_approvals(conn)
    return {
        "ran": "expire_invites",
        "expired_count": expired_count,
        "parent_approval_expired_count": parent_expired_count,
    }


def send_parent_digests() -> dict:
    """Prompt 4A deliverable 5: monthly digest send, one per parent_records
    row with digest_enabled = TRUE. Register on a monthly cron interval.
    """
    settings = get_settings()
    with get_connection(settings) as conn:
        sent_count = parent_service.send_monthly_digests(conn, settings)
    return {"ran": "send_parent_digests", "sent_count": sent_count}


JOB_REGISTRY: dict[str, JobFn] = {
    "noop": noop,
    "expire_invites": expire_invites,
    "send_parent_digests": send_parent_digests,
}


def run_job(job_name: str) -> dict:
    if job_name not in JOB_REGISTRY:
        raise KeyError(f"No job registered under name '{job_name}'")
    return JOB_REGISTRY[job_name]()
