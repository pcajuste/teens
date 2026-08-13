"""Data access for the Insight & Feedback template (Build Prompt 8I
template 4): brand_insight_eligibility (vetting), insight_feedback_campaigns,
insight_feedback_panel_members, insight_feedback_responses.

Enforcement note: no function in this module ever selects talent_id,
display_name, or any other identifying column into a brand-facing
result -- see brand_facing_results() below, which joins through
talent_pseudonyms.handle only. That's the actual enforcement point for
the "brand never sees real identity" guarantee, not an RLS policy (see
the migration's RLS section for why).

brand_facing_results() is also the enforcement point for issue #52's
k-anonymity gate on structured_qa: it withholds all answers for a
campaign (released=False, results=[]) until every panel_size response
has been submitted and moderator-approved via review_response(), so no
individual free-text answer can be correlated back to a specific
early respondent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import asyncpg

# ──────────────────────────────────────────────────────────────────
# brand_insight_eligibility
# ──────────────────────────────────────────────────────────────────

_ELIGIBILITY_COLUMNS = (
    "brand_id, legal_entity_verified, named_contact_verified, business_presence_verified, "
    "funding_confirmed, content_agreement_signed, is_early_stage_startup, "
    "incorporated_3mo_or_backed, has_real_product, manually_reviewed_by, manually_reviewed_at, updated_at"
)


@dataclass(frozen=True, slots=True)
class InsightEligibility:
    brand_id: str
    legal_entity_verified: bool
    named_contact_verified: bool
    business_presence_verified: bool
    funding_confirmed: bool
    content_agreement_signed: bool
    is_early_stage_startup: bool
    incorporated_3mo_or_backed: bool
    has_real_product: bool
    manually_reviewed_by: str | None
    manually_reviewed_at: datetime | None
    updated_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "InsightEligibility":
        return cls(
            brand_id=str(row["brand_id"]),
            legal_entity_verified=row["legal_entity_verified"],
            named_contact_verified=row["named_contact_verified"],
            business_presence_verified=row["business_presence_verified"],
            funding_confirmed=row["funding_confirmed"],
            content_agreement_signed=row["content_agreement_signed"],
            is_early_stage_startup=row["is_early_stage_startup"],
            incorporated_3mo_or_backed=row["incorporated_3mo_or_backed"],
            has_real_product=row["has_real_product"],
            manually_reviewed_by=str(row["manually_reviewed_by"]) if row["manually_reviewed_by"] else None,
            manually_reviewed_at=row["manually_reviewed_at"],
            updated_at=row["updated_at"],
        )

    @property
    def eligible(self) -> bool:
        """Baseline bar every brand must clear, plus the extra
        early-stage-startup bar when applicable (spec: "Extra bar for
        early-stage startups... a real product/prototype to validate,
        and manual (not automated) review for this category
        specifically")."""
        baseline = (
            self.legal_entity_verified
            and self.named_contact_verified
            and self.business_presence_verified
            and self.funding_confirmed
            and self.content_agreement_signed
        )
        if not baseline:
            return False
        if not self.is_early_stage_startup:
            return True
        return (
            self.incorporated_3mo_or_backed
            and self.has_real_product
            and self.manually_reviewed_at is not None
        )


async def get_eligibility(conn: asyncpg.Connection, brand_id: str) -> InsightEligibility | None:
    row = await conn.fetchrow(
        f"SELECT {_ELIGIBILITY_COLUMNS} FROM public.brand_insight_eligibility WHERE brand_id = $1", brand_id
    )
    return InsightEligibility.from_row(row) if row else None


async def upsert_eligibility(
    conn: asyncpg.Connection,
    brand_id: str,
    *,
    legal_entity_verified: bool,
    named_contact_verified: bool,
    business_presence_verified: bool,
    funding_confirmed: bool,
    content_agreement_signed: bool,
    is_early_stage_startup: bool,
    incorporated_3mo_or_backed: bool,
    has_real_product: bool,
) -> InsightEligibility:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.brand_insight_eligibility
          (brand_id, legal_entity_verified, named_contact_verified, business_presence_verified,
           funding_confirmed, content_agreement_signed, is_early_stage_startup,
           incorporated_3mo_or_backed, has_real_product)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (brand_id) DO UPDATE SET
          legal_entity_verified = $2, named_contact_verified = $3, business_presence_verified = $4,
          funding_confirmed = $5, content_agreement_signed = $6, is_early_stage_startup = $7,
          incorporated_3mo_or_backed = $8, has_real_product = $9, updated_at = now()
        RETURNING {_ELIGIBILITY_COLUMNS}
        """,
        brand_id,
        legal_entity_verified,
        named_contact_verified,
        business_presence_verified,
        funding_confirmed,
        content_agreement_signed,
        is_early_stage_startup,
        incorporated_3mo_or_backed,
        has_real_product,
    )
    return InsightEligibility.from_row(row)


async def mark_manually_reviewed(conn: asyncpg.Connection, brand_id: str, *, reviewer_id: str) -> InsightEligibility:
    """Admin-only action -- the startup-validation variant's extra bar
    requires manual review specifically (spec: "manual (not automated)
    review for this category")."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.brand_insight_eligibility
        SET manually_reviewed_by = $2, manually_reviewed_at = now(), updated_at = now()
        WHERE brand_id = $1
        RETURNING {_ELIGIBILITY_COLUMNS}
        """,
        brand_id,
        reviewer_id,
    )
    return InsightEligibility.from_row(row)


# ──────────────────────────────────────────────────────────────────
# insight_feedback_campaigns
# ──────────────────────────────────────────────────────────────────

_CAMPAIGN_COLUMNS = (
    "id, brand_id, title, material_url, business_question, feedback_format, qa_questions, panel_size, "
    "panel_criteria, compensation_cents, confidentiality_terms, is_startup_validation, "
    "opens_at, closes_at, moderation_status, reviewed_by, reviewed_at, rejection_reason, "
    "status, created_at, updated_at"
)


def _load_criteria(raw) -> dict:
    return json.loads(raw) if isinstance(raw, str) else dict(raw or {})


def _load_list(raw) -> list:
    return json.loads(raw) if isinstance(raw, str) else list(raw or [])


@dataclass(frozen=True, slots=True)
class InsightCampaign:
    id: str
    brand_id: str
    title: str
    material_url: str
    business_question: str
    feedback_format: str
    qa_questions: list[dict]
    panel_size: int
    panel_criteria: dict
    compensation_cents: int
    confidentiality_terms: str
    is_startup_validation: bool
    opens_at: datetime | None
    closes_at: datetime | None
    moderation_status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "InsightCampaign":
        return cls(
            id=str(row["id"]),
            brand_id=str(row["brand_id"]),
            title=row["title"],
            material_url=row["material_url"],
            business_question=row["business_question"],
            feedback_format=row["feedback_format"],
            qa_questions=_load_list(row["qa_questions"]),
            panel_size=row["panel_size"],
            panel_criteria=_load_criteria(row["panel_criteria"]),
            compensation_cents=row["compensation_cents"],
            confidentiality_terms=row["confidentiality_terms"],
            is_startup_validation=row["is_startup_validation"],
            opens_at=row["opens_at"],
            closes_at=row["closes_at"],
            moderation_status=row["moderation_status"],
            reviewed_by=str(row["reviewed_by"]) if row["reviewed_by"] else None,
            reviewed_at=row["reviewed_at"],
            rejection_reason=row["rejection_reason"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


async def create_campaign(
    conn: asyncpg.Connection,
    *,
    brand_id: str,
    title: str,
    material_url: str,
    business_question: str,
    panel_size: int,
    panel_criteria: dict,
    compensation_cents: int,
    confidentiality_terms: str,
    is_startup_validation: bool,
    opens_at: datetime | None,
    closes_at: datetime | None,
    feedback_format: str = "rating_scale",
    qa_questions: list[dict] = [],
) -> InsightCampaign:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.insight_feedback_campaigns
          (brand_id, title, material_url, business_question, panel_size, panel_criteria,
           compensation_cents, confidentiality_terms, is_startup_validation, opens_at, closes_at,
           feedback_format, qa_questions)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12, $13::jsonb)
        RETURNING {_CAMPAIGN_COLUMNS}
        """,
        brand_id,
        title,
        material_url,
        business_question,
        panel_size,
        json.dumps(panel_criteria),
        compensation_cents,
        confidentiality_terms,
        is_startup_validation,
        opens_at,
        closes_at,
        feedback_format,
        json.dumps(qa_questions),
    )
    return InsightCampaign.from_row(row)


async def get_by_id(conn: asyncpg.Connection, campaign_id: str) -> InsightCampaign | None:
    row = await conn.fetchrow(f"SELECT {_CAMPAIGN_COLUMNS} FROM public.insight_feedback_campaigns WHERE id = $1", campaign_id)
    return InsightCampaign.from_row(row) if row else None


async def get_by_id_and_brand(conn: asyncpg.Connection, campaign_id: str, brand_id: str) -> InsightCampaign | None:
    row = await conn.fetchrow(
        f"SELECT {_CAMPAIGN_COLUMNS} FROM public.insight_feedback_campaigns WHERE id = $1 AND brand_id = $2",
        campaign_id,
        brand_id,
    )
    return InsightCampaign.from_row(row) if row else None


async def list_for_brand(conn: asyncpg.Connection, brand_id: str) -> list[InsightCampaign]:
    rows = await conn.fetch(
        f"SELECT {_CAMPAIGN_COLUMNS} FROM public.insight_feedback_campaigns WHERE brand_id = $1 ORDER BY created_at DESC",
        brand_id,
    )
    return [InsightCampaign.from_row(r) for r in rows]


async def submit_for_review(conn: asyncpg.Connection, campaign_id: str) -> InsightCampaign:
    row = await conn.fetchrow(
        f"""
        UPDATE public.insight_feedback_campaigns SET moderation_status = 'pending_review', updated_at = now()
        WHERE id = $1 RETURNING {_CAMPAIGN_COLUMNS}
        """,
        campaign_id,
    )
    return InsightCampaign.from_row(row)


async def review(
    conn: asyncpg.Connection, campaign_id: str, *, approved: bool, reviewer_id: str, rejection_reason: str | None
) -> InsightCampaign:
    row = await conn.fetchrow(
        f"""
        UPDATE public.insight_feedback_campaigns
        SET moderation_status = $2, reviewed_by = $3, reviewed_at = now(), rejection_reason = $4, updated_at = now()
        WHERE id = $1
        RETURNING {_CAMPAIGN_COLUMNS}
        """,
        campaign_id,
        "approved" if approved else "rejected",
        reviewer_id,
        rejection_reason,
    )
    return InsightCampaign.from_row(row)


async def list_pending_review(conn: asyncpg.Connection) -> list[InsightCampaign]:
    rows = await conn.fetch(
        f"SELECT {_CAMPAIGN_COLUMNS} FROM public.insight_feedback_campaigns WHERE moderation_status = 'pending_review' ORDER BY created_at ASC"
    )
    return [InsightCampaign.from_row(r) for r in rows]


async def activate_campaign(conn: asyncpg.Connection, campaign_id: str) -> InsightCampaign:
    row = await conn.fetchrow(
        f"""
        UPDATE public.insight_feedback_campaigns SET status = 'active', updated_at = now()
        WHERE id = $1 RETURNING {_CAMPAIGN_COLUMNS}
        """,
        campaign_id,
    )
    return InsightCampaign.from_row(row)


# ──────────────────────────────────────────────────────────────────
# panel selection + membership
# ──────────────────────────────────────────────────────────────────


async def select_eligible_talent_ids(
    conn: asyncpg.Connection, *, categories: list[str] | None, min_graduation_year: int | None, limit: int
) -> list[str]:
    """System-driven panel selection (spec: "panel size and criteria...
    brand cannot hand-select individual teens"). Only opted-in talents
    (insight_feedback_opt_in = TRUE) are eligible at all; ORDER BY
    random() so which subset of an oversized eligible pool gets invited
    isn't influenced by any brand-visible signal like profile
    completeness or rating."""
    rows = await conn.fetch(
        """
        SELECT id FROM public.talent_profiles
        WHERE insight_feedback_opt_in = TRUE
          AND ($1::text[] IS NULL OR categories && $1::text[])
          AND ($2::int IS NULL OR graduation_year >= $2)
        ORDER BY random()
        LIMIT $3
        """,
        categories or None,
        min_graduation_year,
        limit,
    )
    return [str(r["id"]) for r in rows]


async def add_panel_members(
    conn: asyncpg.Connection, *, campaign_id: str, talent_ids: list[str], pseudonym_ids: dict[str, str]
) -> None:
    for talent_id in talent_ids:
        await conn.execute(
            """
            INSERT INTO public.insight_feedback_panel_members (campaign_id, talent_id, pseudonym_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (campaign_id, talent_id) DO NOTHING
            """,
            campaign_id,
            talent_id,
            pseudonym_ids[talent_id],
        )


@dataclass(frozen=True, slots=True)
class PanelInvitation:
    panel_member_id: str
    campaign_id: str
    campaign_title: str
    business_question: str
    feedback_format: str
    qa_questions: list[dict]
    confidentiality_terms: str
    compensation_cents: int
    invited_at: datetime
    responded_at: datetime | None


async def list_invitations_for_talent(conn: asyncpg.Connection, talent_id: str) -> list[PanelInvitation]:
    rows = await conn.fetch(
        """
        SELECT m.id AS panel_member_id, c.id AS campaign_id, c.title AS campaign_title,
               c.business_question, c.feedback_format, c.qa_questions,
               c.confidentiality_terms, c.compensation_cents,
               m.invited_at, m.responded_at
        FROM public.insight_feedback_panel_members m
        JOIN public.insight_feedback_campaigns c ON c.id = m.campaign_id
        WHERE m.talent_id = $1
        ORDER BY m.invited_at DESC
        """,
        talent_id,
    )
    return [
        PanelInvitation(
            panel_member_id=str(r["panel_member_id"]),
            campaign_id=str(r["campaign_id"]),
            campaign_title=r["campaign_title"],
            business_question=r["business_question"],
            feedback_format=r["feedback_format"],
            qa_questions=_load_list(r["qa_questions"]),
            confidentiality_terms=r["confidentiality_terms"],
            compensation_cents=r["compensation_cents"],
            invited_at=r["invited_at"],
            responded_at=r["responded_at"],
        )
        for r in rows
    ]


async def get_panel_member_for_talent(conn: asyncpg.Connection, panel_member_id: str, talent_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT id, campaign_id, talent_id FROM public.insight_feedback_panel_members WHERE id = $1 AND talent_id = $2",
        panel_member_id,
        talent_id,
    )


async def mark_responded(conn: asyncpg.Connection, panel_member_id: str) -> None:
    await conn.execute(
        "UPDATE public.insight_feedback_panel_members SET responded_at = now() WHERE id = $1", panel_member_id
    )


# ──────────────────────────────────────────────────────────────────
# responses
# ──────────────────────────────────────────────────────────────────


async def submit_response(
    conn: asyncpg.Connection,
    *,
    panel_member_id: str,
    feedback_format: str,
    ratings: list[dict] | None = None,
    qa_answers: list[dict] | None = None,
    scrub_flags: list[dict] | None = None,
) -> datetime:
    """rating_scale rows are cleared immediately (moderation_status
    'approved') -- a 1-5 score carries no PII risk. structured_qa rows
    start 'pending_review' and require an admin to approve/reject via
    review_response() before brand_facing_results() will ever surface
    them -- no response is auto-cleared to the brand (issue #52)."""
    moderation_status = "approved" if feedback_format == "rating_scale" else "pending_review"
    row = await conn.fetchrow(
        """
        INSERT INTO public.insight_feedback_responses
          (campaign_id, panel_member_id, ratings, qa_answers, moderation_status, scrub_flags)
        SELECT campaign_id, id, $2::jsonb, $3::jsonb, $4, $5::jsonb
        FROM public.insight_feedback_panel_members WHERE id = $1
        RETURNING submitted_at
        """,
        panel_member_id,
        json.dumps(ratings or []),
        json.dumps(qa_answers) if qa_answers is not None else None,
        moderation_status,
        json.dumps(scrub_flags or []),
    )
    return row["submitted_at"]


async def has_responded(conn: asyncpg.Connection, panel_member_id: str) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM public.insight_feedback_responses WHERE panel_member_id = $1", panel_member_id
    )
    return row is not None


async def brand_facing_results(conn: asyncpg.Connection, campaign_id: str) -> dict:
    """The one and only brand-facing read of response data. Selects
    talent_pseudonyms.handle and nothing from talent_profiles or
    users -- see this module's docstring. Also the enforcement point
    for issue #52's k-anonymity gate: structured_qa answers are
    withheld in full (results=[], released=False) until every
    panel_size response has been submitted *and* moderator-approved,
    so a brand can never correlate an early individual response back
    to "whoever answered first." rating_scale keeps its pre-existing
    per-response release behavior -- numeric scores were never the
    risk #52 flagged."""
    campaign = await conn.fetchrow(
        "SELECT feedback_format, panel_size FROM public.insight_feedback_campaigns WHERE id = $1", campaign_id
    )
    feedback_format = campaign["feedback_format"]
    panel_size = campaign["panel_size"]

    if feedback_format == "rating_scale":
        rows = await conn.fetch(
            """
            SELECT p.handle AS pseudonym_handle, r.ratings, r.submitted_at
            FROM public.insight_feedback_responses r
            JOIN public.insight_feedback_panel_members m ON m.id = r.panel_member_id
            JOIN public.talent_pseudonyms p ON p.id = m.pseudonym_id
            WHERE r.campaign_id = $1
            ORDER BY r.submitted_at ASC
            """,
            campaign_id,
        )
        results = [
            {
                "pseudonym_handle": r["pseudonym_handle"],
                "feedback_format": feedback_format,
                "ratings": _load_list(r["ratings"]),
                "qa_answers": None,
                "submitted_at": r["submitted_at"],
            }
            for r in rows
        ]
        return {
            "feedback_format": feedback_format,
            "released": True,
            "responses_submitted": len(results),
            "responses_required": panel_size,
            "results": results,
        }

    approved_count = await conn.fetchval(
        "SELECT count(*) FROM public.insight_feedback_responses WHERE campaign_id = $1 AND moderation_status = 'approved'",
        campaign_id,
    )
    if approved_count < panel_size:
        return {
            "feedback_format": feedback_format,
            "released": False,
            "responses_submitted": approved_count,
            "responses_required": panel_size,
            "results": [],
        }

    rows = await conn.fetch(
        """
        SELECT p.handle AS pseudonym_handle, r.qa_answers, r.submitted_at
        FROM public.insight_feedback_responses r
        JOIN public.insight_feedback_panel_members m ON m.id = r.panel_member_id
        JOIN public.talent_pseudonyms p ON p.id = m.pseudonym_id
        WHERE r.campaign_id = $1 AND r.moderation_status = 'approved'
        ORDER BY r.submitted_at ASC
        """,
        campaign_id,
    )
    results = [
        {
            "pseudonym_handle": r["pseudonym_handle"],
            "feedback_format": feedback_format,
            "ratings": None,
            "qa_answers": _load_list(r["qa_answers"]),
            "submitted_at": r["submitted_at"],
        }
        for r in rows
    ]
    return {
        "feedback_format": feedback_format,
        "released": True,
        "responses_submitted": approved_count,
        "responses_required": panel_size,
        "results": results,
    }


async def list_pending_response_reviews(conn: asyncpg.Connection) -> list[dict]:
    """Admin moderation queue for structured_qa responses. Joins
    through talent_pseudonyms.handle only, same as brand_facing_results
    above -- a human reviewer moderating text still doesn't need the
    talent's real identity, and keeping this query pseudonymous avoids
    setting a weaker precedent a future change might accidentally reuse
    for an actual brand-facing path."""
    rows = await conn.fetch(
        """
        SELECT r.id, r.campaign_id, c.title AS campaign_title, p.handle AS pseudonym_handle,
               r.qa_answers, r.scrub_flags, r.submitted_at
        FROM public.insight_feedback_responses r
        JOIN public.insight_feedback_panel_members m ON m.id = r.panel_member_id
        JOIN public.talent_pseudonyms p ON p.id = m.pseudonym_id
        JOIN public.insight_feedback_campaigns c ON c.id = r.campaign_id
        WHERE r.moderation_status = 'pending_review'
        ORDER BY r.submitted_at ASC
        """
    )
    return [
        {
            "id": str(r["id"]),
            "campaign_id": str(r["campaign_id"]),
            "campaign_title": r["campaign_title"],
            "pseudonym_handle": r["pseudonym_handle"],
            "qa_answers": _load_list(r["qa_answers"]),
            "scrub_flags": _load_list(r["scrub_flags"]),
            "submitted_at": r["submitted_at"],
        }
        for r in rows
    ]


async def review_response(
    conn: asyncpg.Connection, response_id: str, *, approved: bool, reviewer_id: str, rejection_reason: str | None
) -> None:
    """A rejected response never counts toward brand_facing_results()'s
    k-anonymity threshold -- known, unhandled-this-pass consequence: a
    campaign with enough rejections may never reach panel_size approved
    responses (no re-invite/backfill mechanism exists yet)."""
    await conn.execute(
        """
        UPDATE public.insight_feedback_responses
        SET moderation_status = $2, reviewed_by = $3, reviewed_at = now(), rejection_reason = $4
        WHERE id = $1
        """,
        response_id,
        "approved" if approved else "rejected",
        reviewer_id,
        rejection_reason,
    )


async def talent_own_insight_history(conn: asyncpg.Connection, talent_id: str) -> list[dict]:
    """The teen's own real-named record: "Insight Session Completed"
    entries (spec: "the teen always knows it's them")."""
    rows = await conn.fetch(
        """
        SELECT c.title AS campaign_title, r.submitted_at
        FROM public.insight_feedback_responses r
        JOIN public.insight_feedback_panel_members m ON m.id = r.panel_member_id
        JOIN public.insight_feedback_campaigns c ON c.id = m.campaign_id
        WHERE m.talent_id = $1
        ORDER BY r.submitted_at DESC
        """,
        talent_id,
    )
    return [{"campaign_title": r["campaign_title"], "submitted_at": r["submitted_at"]} for r in rows]


async def parent_dashboard_activity(conn: asyncpg.Connection, talent_id: str) -> dict:
    """GET /parent/dashboard's insight_feedback_activity block.
    confidentiality_terms is included per
    insight_feedback_campaigns.confidentiality_terms's own column
    comment ("shown to teen + parent before joining") -- this is the
    parent-facing half of that requirement. Uses talent_id directly
    (never pseudonym_id) since this is the teen's own real-named
    record, same trust boundary as talent_own_insight_history above --
    not the brand-facing path."""
    totals = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total_invited,
            COUNT(*) FILTER (WHERE m.responded_at IS NOT NULL) AS total_responded,
            COALESCE(SUM(c.compensation_cents) FILTER (WHERE m.responded_at IS NOT NULL), 0) AS total_earned_cents
        FROM public.insight_feedback_panel_members m
        JOIN public.insight_feedback_campaigns c ON c.id = m.campaign_id
        WHERE m.talent_id = $1
        """,
        talent_id,
    )
    recent = await conn.fetch(
        """
        SELECT c.title AS campaign_title, c.confidentiality_terms, c.compensation_cents,
               m.invited_at, m.responded_at
        FROM public.insight_feedback_panel_members m
        JOIN public.insight_feedback_campaigns c ON c.id = m.campaign_id
        WHERE m.talent_id = $1
        ORDER BY m.invited_at DESC
        LIMIT 5
        """,
        talent_id,
    )
    return {
        "total_invited": totals["total_invited"],
        "total_responded": totals["total_responded"],
        "total_earned_cents": totals["total_earned_cents"],
        "recent_invitations": [
            {
                "campaign_title": r["campaign_title"],
                "confidentiality_terms": r["confidentiality_terms"],
                "invited_at": r["invited_at"],
                "status": "responded" if r["responded_at"] is not None else "invited",
                "compensation_cents": r["compensation_cents"] if r["responded_at"] is not None else None,
            }
            for r in recent
        ],
    }
