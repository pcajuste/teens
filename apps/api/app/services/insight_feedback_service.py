"""Orchestration for the Insight & Feedback template (Build Prompt 8I
template 4): the vetting gate and system-driven panel assignment. Kept
out of the router so activate_campaign's two-step "check eligibility,
then fill the panel" isn't duplicated between the route handler and any
future caller (e.g. an admin re-run)."""
from __future__ import annotations

from datetime import datetime

import asyncpg

from app.repositories import insight_feedback_repository
from app.services import pseudonym_service, text_moderation_service


class InsightNotEligibleError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class UnknownQuestionIdError(Exception):
    def __init__(self, unknown_ids: list[str]) -> None:
        self.unknown_ids = unknown_ids
        super().__init__(f"qa_answers reference unknown question_id(s): {unknown_ids}")


class InsufficientPanelError(Exception):
    def __init__(self, available: int, needed: int) -> None:
        self.available = available
        self.needed = needed
        super().__init__(f"Only {available} opted-in talents match this campaign's criteria; {needed} needed.")


async def require_eligible_brand(conn: asyncpg.Connection, brand_id: str) -> None:
    eligibility = await insight_feedback_repository.get_eligibility(conn, brand_id)
    if eligibility is None or not eligibility.eligible:
        raise InsightNotEligibleError(
            "This brand has not cleared the Insight & Feedback vetting requirements yet. "
            "Complete PUT /brands/insight-eligibility first."
        )


async def activate_with_panel(
    conn: asyncpg.Connection, campaign: insight_feedback_repository.InsightCampaign
) -> insight_feedback_repository.InsightCampaign:
    """Fills the panel from the opted-in, criteria-matching talent pool,
    generates/reuses each selected talent's pseudonym, then flips the
    campaign live. All in the caller's existing connection/transaction
    -- if panel fill comes up short, nothing is written and the brand
    sees InsufficientPanelError rather than a half-filled live campaign."""
    criteria = campaign.panel_criteria or {}
    eligible_ids = await insight_feedback_repository.select_eligible_talent_ids(
        conn,
        categories=criteria.get("categories"),
        min_graduation_year=criteria.get("min_graduation_year"),
        limit=campaign.panel_size,
    )
    if len(eligible_ids) < campaign.panel_size:
        raise InsufficientPanelError(available=len(eligible_ids), needed=campaign.panel_size)

    pseudonym_ids = {}
    for talent_id in eligible_ids:
        pseudonym = await pseudonym_service.get_or_create_pseudonym(conn, talent_id)
        pseudonym_ids[talent_id] = pseudonym.id

    await insight_feedback_repository.add_panel_members(
        conn, campaign_id=campaign.id, talent_ids=eligible_ids, pseudonym_ids=pseudonym_ids
    )
    return await insight_feedback_repository.activate_campaign(conn, campaign.id)


async def submit_structured_qa_response(
    conn: asyncpg.Connection,
    *,
    panel_member_id: str,
    campaign: insight_feedback_repository.InsightCampaign,
    qa_answers: list[dict],
) -> datetime:
    """Validates the submitted answers against the campaign's fixed
    question set, runs the PII scrubber, then writes the response as
    'pending_review' (submit_response() decides that internally from
    feedback_format) -- no structured_qa response is ever auto-cleared
    to the brand (issue #52)."""
    known_ids = {q["id"] for q in campaign.qa_questions}
    submitted_ids = {a["question_id"] for a in qa_answers}
    unknown_ids = sorted(submitted_ids - known_ids)
    if unknown_ids:
        raise UnknownQuestionIdError(unknown_ids)

    scrub_flags = text_moderation_service.scrub_answers(qa_answers)
    return await insight_feedback_repository.submit_response(
        conn,
        panel_member_id=panel_member_id,
        feedback_format="structured_qa",
        qa_answers=qa_answers,
        scrub_flags=scrub_flags,
    )
