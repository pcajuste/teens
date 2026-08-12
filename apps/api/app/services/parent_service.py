"""Parent-portal service shell. Prompt 4A.

Every function here respects the parent-facing data minimization
boundary (Section 9A): no recruiter message content, no submission
text/files, no brand contact details ever cross into a parent-facing
send or record.
"""
from __future__ import annotations


async def send_digest_email(parent_id: str) -> None:
    """Send the monthly digest (campaigns completed, earnings, profile-
    completeness change, active categories only). Triggered by the
    scheduled job registered in app/jobs/runner.py."""
    raise NotImplementedError


async def send_campaign_approval_request(parent_id: str, campaign_rep_id: str) -> None:
    """Notify a parent that a campaign is awaiting their approval, for
    under-16 reps (or 16-17 reps with campaign_approval_required=TRUE)."""
    raise NotImplementedError


async def record_campaign_approval(parent_id: str, campaign_rep_id: str) -> None:
    """Record a parent's approval for a pending campaign_reps row."""
    raise NotImplementedError


async def record_campaign_block(parent_id: str, campaign_rep_id: str) -> None:
    """Record a parent's block/decline for a pending campaign_reps row."""
    raise NotImplementedError


async def apply_values_filter(rep_id: str, campaign_category: str) -> bool:
    """Return True if `campaign_category` is allowed for `rep_id` under
    their parent's values_filters. Enforced server-side in
    GET /reps/campaigns/available (Section 8) — the rep never sees a
    blocked-category campaign as an option."""
    raise NotImplementedError
