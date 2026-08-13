"""Build Prompt 8I: Scholarship template (brand + talent) and Insight &
Feedback template (brand + talent), including the vetting gate and
system-driven panel assignment. Company Profile lives in routers/brands.py
(GET/PUT /brands/me/company-profile); the Skills Challenge template's new
fields/moderation gate live in routers/challenges.py.
"""
from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import AuthenticatedUser, require_role
from app.db.pool import get_connection
from app.repositories import (
    brand_profiles_repository,
    insight_feedback_repository,
    internships_repository,
    scholarships_repository,
    talent_profiles_repository,
)
from app.schemas.content_templates import (
    InsightBrandResultResponse,
    InsightBrandResultsResponse,
    InsightCampaignCreateRequest,
    InsightCampaignResponse,
    InsightEligibilityResponse,
    InsightEligibilityUpdateRequest,
    InsightInvitationResponse,
    InsightResponseAck,
    InsightResponseSubmitRequest,
    InternshipApplicationBrandView,
    InternshipApplicationResponse,
    InternshipApplyRequest,
    InternshipCreateRequest,
    InternshipResponse,
    ScholarshipApplicationBrandView,
    ScholarshipApplicationResponse,
    ScholarshipApplyRequest,
    ScholarshipCreateRequest,
    ScholarshipResponse,
)
from app.services import insight_feedback_service, pseudonym_service

brands_scholarships_router = APIRouter(prefix="/brands/scholarships", tags=["content-templates"])
talents_scholarships_router = APIRouter(prefix="/talents/scholarships", tags=["content-templates"])
brands_internships_router = APIRouter(prefix="/brands/internships", tags=["content-templates"])
talents_internships_router = APIRouter(prefix="/talents/internships", tags=["content-templates"])
brands_insight_router = APIRouter(prefix="/brands/insight", tags=["content-templates"])
talents_insight_router = APIRouter(prefix="/talents/insight", tags=["content-templates"])


async def _get_own_brand_profile(conn: asyncpg.Connection, user: AuthenticatedUser) -> brand_profiles_repository.BrandProfile:
    profile = await brand_profiles_repository.get_by_user_id(conn, user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "brand_profile_not_found", "message": "Complete onboarding via PUT /brands/me first."},
        )
    return profile


async def _get_own_talent_profile(conn: asyncpg.Connection, user: AuthenticatedUser) -> talent_profiles_repository.TalentProfile:
    profile = await talent_profiles_repository.get_by_user_id(conn, user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "talent_profile_not_found", "message": "Complete onboarding via PUT /talents/me first."},
        )
    return profile


def _require_company_profile_complete(brand: brand_profiles_repository.BrandProfile) -> None:
    """8I: "the brand's home base, required before any campaign goes
    live." Checked at creation time for every template below."""
    if not brand.company_profile_complete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "company_profile_incomplete",
                "message": "Complete your Company Profile (logo, about, why-on-Teenure) before creating campaign content.",
            },
        )


# ══════════════════════════════════════════════════════════════════
# /brands/scholarships
# ══════════════════════════════════════════════════════════════════


def _to_scholarship_response(s: scholarships_repository.Scholarship) -> ScholarshipResponse:
    return ScholarshipResponse(
        id=s.id,
        title=s.title,
        award_amount_cents=s.award_amount_cents,
        number_of_awards=s.number_of_awards,
        eligibility_criteria=s.eligibility_criteria,
        application_requirements=s.application_requirements,
        why_text=s.why_text,
        image_url=s.image_url,
        video_url=s.video_url,
        deadline=s.deadline,
        moderation_status=s.moderation_status,
        rejection_reason=s.rejection_reason,
        status=s.status,
        created_at=s.created_at,
    )


async def _require_owned_scholarship(conn: asyncpg.Connection, scholarship_id: str, brand_id: str) -> scholarships_repository.Scholarship:
    scholarship = await scholarships_repository.get_by_id_and_brand(conn, scholarship_id, brand_id)
    if scholarship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "scholarship_not_found", "message": "No scholarship found for that id."},
        )
    return scholarship


@brands_scholarships_router.post("", response_model=ScholarshipResponse, status_code=status.HTTP_201_CREATED)
async def create_scholarship(
    body: ScholarshipCreateRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ScholarshipResponse:
    brand = await _get_own_brand_profile(conn, user)
    _require_company_profile_complete(brand)
    scholarship = await scholarships_repository.create(
        conn,
        brand_id=brand.id,
        title=body.title,
        award_amount_cents=body.award_amount_cents,
        number_of_awards=body.number_of_awards,
        eligibility_criteria=[c.model_dump() for c in body.eligibility_criteria],
        application_requirements=body.application_requirements,
        why_text=body.why_text,
        image_url=body.image_url,
        video_url=body.video_url,
        deadline=body.deadline,
    )
    return _to_scholarship_response(scholarship)


@brands_scholarships_router.get("", response_model=list[ScholarshipResponse])
async def list_own_scholarships(
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[ScholarshipResponse]:
    brand = await _get_own_brand_profile(conn, user)
    rows = await scholarships_repository.list_for_brand(conn, brand.id)
    return [_to_scholarship_response(s) for s in rows]


@brands_scholarships_router.post("/{scholarship_id}/submit-for-review", response_model=ScholarshipResponse)
async def submit_scholarship_for_review(
    scholarship_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ScholarshipResponse:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_scholarship(conn, scholarship_id, brand.id)
    updated = await scholarships_repository.submit_for_review(conn, scholarship_id)
    return _to_scholarship_response(updated)


@brands_scholarships_router.post("/{scholarship_id}/activate", response_model=ScholarshipResponse)
async def activate_scholarship(
    scholarship_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ScholarshipResponse:
    """Self-service to build, human review to publish (8I content
    rules) -- go-live is gated on moderation_status='approved', both
    here (clean 400) and at the DB layer (CHECK constraint backstop)."""
    brand = await _get_own_brand_profile(conn, user)
    scholarship = await _require_owned_scholarship(conn, scholarship_id, brand.id)
    if scholarship.moderation_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "not_approved", "message": "This scholarship has not been approved by Teenure review yet."},
        )
    updated = await scholarships_repository.activate(conn, scholarship_id)
    return _to_scholarship_response(updated)


@brands_scholarships_router.post("/{scholarship_id}/close", response_model=ScholarshipResponse)
async def close_scholarship(
    scholarship_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ScholarshipResponse:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_scholarship(conn, scholarship_id, brand.id)
    updated = await scholarships_repository.close(conn, scholarship_id)
    return _to_scholarship_response(updated)


@brands_scholarships_router.get("/{scholarship_id}/applications", response_model=list[ScholarshipApplicationBrandView])
async def list_scholarship_applications(
    scholarship_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[ScholarshipApplicationBrandView]:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_scholarship(conn, scholarship_id, brand.id)
    applications = await scholarships_repository.list_for_scholarship(conn, scholarship_id)
    return [
        ScholarshipApplicationBrandView(
            id=a.id, talent_id=a.talent_id, response_text=a.response_text, status=a.status, submitted_at=a.submitted_at
        )
        for a in applications
    ]


@brands_scholarships_router.post(
    "/{scholarship_id}/applications/{application_id}/award", response_model=ScholarshipApplicationBrandView
)
async def award_scholarship_application(
    scholarship_id: str,
    application_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ScholarshipApplicationBrandView:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_scholarship(conn, scholarship_id, brand.id)
    updated = await scholarships_repository.set_application_status(conn, application_id, "awarded")
    return ScholarshipApplicationBrandView(
        id=updated.id, talent_id=updated.talent_id, response_text=updated.response_text,
        status=updated.status, submitted_at=updated.submitted_at,
    )


@brands_scholarships_router.post(
    "/{scholarship_id}/applications/{application_id}/decline", response_model=ScholarshipApplicationBrandView
)
async def decline_scholarship_application(
    scholarship_id: str,
    application_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ScholarshipApplicationBrandView:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_scholarship(conn, scholarship_id, brand.id)
    updated = await scholarships_repository.set_application_status(conn, application_id, "declined")
    return ScholarshipApplicationBrandView(
        id=updated.id, talent_id=updated.talent_id, response_text=updated.response_text,
        status=updated.status, submitted_at=updated.submitted_at,
    )


# ══════════════════════════════════════════════════════════════════
# /talents/scholarships
# ══════════════════════════════════════════════════════════════════


@talents_scholarships_router.get("/available", response_model=list[ScholarshipResponse])
async def available_scholarships(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[ScholarshipResponse]:
    rows = await scholarships_repository.list_active(conn)
    return [_to_scholarship_response(s) for s in rows]


@talents_scholarships_router.post(
    "/{scholarship_id}/apply", response_model=ScholarshipApplicationResponse, status_code=status.HTTP_201_CREATED
)
async def apply_to_scholarship(
    scholarship_id: str,
    body: ScholarshipApplyRequest,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ScholarshipApplicationResponse:
    profile = await _get_own_talent_profile(conn, user)
    scholarship = await scholarships_repository.get_by_id(conn, scholarship_id)
    if scholarship is None or scholarship.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "scholarship_not_found", "message": "No active scholarship found for that id."},
        )
    if await scholarships_repository.has_applied(conn, scholarship_id=scholarship_id, talent_id=profile.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "already_applied", "message": "You've already applied to this scholarship."},
        )
    application = await scholarships_repository.apply(
        conn, scholarship_id=scholarship_id, talent_id=profile.id, response_text=body.response_text
    )
    return ScholarshipApplicationResponse(
        id=application.id, scholarship_id=application.scholarship_id, response_text=application.response_text,
        status=application.status, submitted_at=application.submitted_at, reviewed_at=application.reviewed_at,
    )


@talents_scholarships_router.get("/applications", response_model=list[ScholarshipApplicationResponse])
async def my_scholarship_applications(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[ScholarshipApplicationResponse]:
    profile = await _get_own_talent_profile(conn, user)
    rows = await scholarships_repository.list_for_talent(conn, profile.id)
    return [
        ScholarshipApplicationResponse(
            id=a.id, scholarship_id=a.scholarship_id, response_text=a.response_text,
            status=a.status, submitted_at=a.submitted_at, reviewed_at=a.reviewed_at,
        )
        for a in rows
    ]


# ══════════════════════════════════════════════════════════════════
# /brands/internships & /talents/internships (issue #50) -- same
# lifecycle shape as /brands/scholarships above.
# ══════════════════════════════════════════════════════════════════


def _to_internship_response(i: internships_repository.Internship) -> InternshipResponse:
    return InternshipResponse(
        id=i.id,
        role_title=i.role_title,
        description=i.description,
        time_commitment=i.time_commitment,
        compensation_type=i.compensation_type,
        compensation_why=i.compensation_why,
        requirements_text=i.requirements_text,
        application_process_text=i.application_process_text,
        why_text=i.why_text,
        deadline=i.deadline,
        moderation_status=i.moderation_status,
        rejection_reason=i.rejection_reason,
        status=i.status,
        created_at=i.created_at,
    )


async def _require_owned_internship(conn: asyncpg.Connection, internship_id: str, brand_id: str) -> internships_repository.Internship:
    internship = await internships_repository.get_by_id_and_brand(conn, internship_id, brand_id)
    if internship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "internship_not_found", "message": "No internship found for that id."},
        )
    return internship


@brands_internships_router.post("", response_model=InternshipResponse, status_code=status.HTTP_201_CREATED)
async def create_internship(
    body: InternshipCreateRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InternshipResponse:
    brand = await _get_own_brand_profile(conn, user)
    _require_company_profile_complete(brand)
    internship = await internships_repository.create(
        conn,
        brand_id=brand.id,
        role_title=body.role_title,
        description=body.description,
        time_commitment=body.time_commitment,
        compensation_type=body.compensation_type,
        compensation_why=body.compensation_why,
        requirements_text=body.requirements_text,
        application_process_text=body.application_process_text,
        why_text=body.why_text,
        deadline=body.deadline,
    )
    return _to_internship_response(internship)


@brands_internships_router.get("", response_model=list[InternshipResponse])
async def list_own_internships(
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[InternshipResponse]:
    brand = await _get_own_brand_profile(conn, user)
    rows = await internships_repository.list_for_brand(conn, brand.id)
    return [_to_internship_response(i) for i in rows]


@brands_internships_router.post("/{internship_id}/submit-for-review", response_model=InternshipResponse)
async def submit_internship_for_review(
    internship_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InternshipResponse:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_internship(conn, internship_id, brand.id)
    updated = await internships_repository.submit_for_review(conn, internship_id)
    return _to_internship_response(updated)


@brands_internships_router.post("/{internship_id}/activate", response_model=InternshipResponse)
async def activate_internship(
    internship_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InternshipResponse:
    """Self-service to build, human review to publish (8I content
    rules) -- go-live is gated on moderation_status='approved', both
    here (clean 400) and at the DB layer (CHECK constraint backstop).
    Carries the same review gate as every other template despite the
    added legal weight (minors + labor/earnings) -- that weight is
    handled by the reviewer's own judgment on this queue, not a
    separate code path."""
    brand = await _get_own_brand_profile(conn, user)
    internship = await _require_owned_internship(conn, internship_id, brand.id)
    if internship.moderation_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "not_approved", "message": "This internship has not been approved by Teenure review yet."},
        )
    updated = await internships_repository.activate(conn, internship_id)
    return _to_internship_response(updated)


@brands_internships_router.post("/{internship_id}/close", response_model=InternshipResponse)
async def close_internship(
    internship_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InternshipResponse:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_internship(conn, internship_id, brand.id)
    updated = await internships_repository.close(conn, internship_id)
    return _to_internship_response(updated)


@brands_internships_router.get("/{internship_id}/applications", response_model=list[InternshipApplicationBrandView])
async def list_internship_applications(
    internship_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[InternshipApplicationBrandView]:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_internship(conn, internship_id, brand.id)
    applications = await internships_repository.list_for_internship(conn, internship_id)
    return [
        InternshipApplicationBrandView(
            id=a.id, talent_id=a.talent_id, response_text=a.response_text, status=a.status, submitted_at=a.submitted_at
        )
        for a in applications
    ]


@brands_internships_router.post(
    "/{internship_id}/applications/{application_id}/accept", response_model=InternshipApplicationBrandView
)
async def accept_internship_application(
    internship_id: str,
    application_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InternshipApplicationBrandView:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_internship(conn, internship_id, brand.id)
    updated = await internships_repository.set_application_status(conn, application_id, "accepted")
    return InternshipApplicationBrandView(
        id=updated.id, talent_id=updated.talent_id, response_text=updated.response_text,
        status=updated.status, submitted_at=updated.submitted_at,
    )


@brands_internships_router.post(
    "/{internship_id}/applications/{application_id}/decline", response_model=InternshipApplicationBrandView
)
async def decline_internship_application(
    internship_id: str,
    application_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InternshipApplicationBrandView:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_internship(conn, internship_id, brand.id)
    updated = await internships_repository.set_application_status(conn, application_id, "declined")
    return InternshipApplicationBrandView(
        id=updated.id, talent_id=updated.talent_id, response_text=updated.response_text,
        status=updated.status, submitted_at=updated.submitted_at,
    )


@talents_internships_router.get("/available", response_model=list[InternshipResponse])
async def available_internships(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[InternshipResponse]:
    rows = await internships_repository.list_active(conn)
    return [_to_internship_response(i) for i in rows]


@talents_internships_router.post(
    "/{internship_id}/apply", response_model=InternshipApplicationResponse, status_code=status.HTTP_201_CREATED
)
async def apply_to_internship(
    internship_id: str,
    body: InternshipApplyRequest,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InternshipApplicationResponse:
    profile = await _get_own_talent_profile(conn, user)
    internship = await internships_repository.get_by_id(conn, internship_id)
    if internship is None or internship.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "internship_not_found", "message": "No active internship found for that id."},
        )
    if await internships_repository.has_applied(conn, internship_id=internship_id, talent_id=profile.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "already_applied", "message": "You've already applied to this internship."},
        )
    application = await internships_repository.apply(
        conn, internship_id=internship_id, talent_id=profile.id, response_text=body.response_text
    )
    return InternshipApplicationResponse(
        id=application.id, internship_id=application.internship_id, response_text=application.response_text,
        status=application.status, submitted_at=application.submitted_at, reviewed_at=application.reviewed_at,
    )


@talents_internships_router.get("/applications", response_model=list[InternshipApplicationResponse])
async def my_internship_applications(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[InternshipApplicationResponse]:
    profile = await _get_own_talent_profile(conn, user)
    rows = await internships_repository.list_for_talent(conn, profile.id)
    return [
        InternshipApplicationResponse(
            id=a.id, internship_id=a.internship_id, response_text=a.response_text,
            status=a.status, submitted_at=a.submitted_at, reviewed_at=a.reviewed_at,
        )
        for a in rows
    ]


# ══════════════════════════════════════════════════════════════════
# /brands/insight -- vetting + campaign CRUD + results
# ══════════════════════════════════════════════════════════════════


def _to_eligibility_response(e: insight_feedback_repository.InsightEligibility) -> InsightEligibilityResponse:
    return InsightEligibilityResponse(
        legal_entity_verified=e.legal_entity_verified,
        named_contact_verified=e.named_contact_verified,
        business_presence_verified=e.business_presence_verified,
        funding_confirmed=e.funding_confirmed,
        content_agreement_signed=e.content_agreement_signed,
        is_early_stage_startup=e.is_early_stage_startup,
        incorporated_3mo_or_backed=e.incorporated_3mo_or_backed,
        has_real_product=e.has_real_product,
        eligible=e.eligible,
        manually_reviewed_at=e.manually_reviewed_at,
    )


@brands_insight_router.get("/eligibility", response_model=InsightEligibilityResponse)
async def get_insight_eligibility(
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InsightEligibilityResponse:
    brand = await _get_own_brand_profile(conn, user)
    existing = await insight_feedback_repository.get_eligibility(conn, brand.id)
    if existing is None:
        existing = await insight_feedback_repository.upsert_eligibility(
            conn, brand.id, legal_entity_verified=False, named_contact_verified=False,
            business_presence_verified=False, funding_confirmed=False, content_agreement_signed=False,
            is_early_stage_startup=False, incorporated_3mo_or_backed=False, has_real_product=False,
        )
    return _to_eligibility_response(existing)


@brands_insight_router.put("/eligibility", response_model=InsightEligibilityResponse)
async def put_insight_eligibility(
    body: InsightEligibilityUpdateRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InsightEligibilityResponse:
    """Self-attested fields a brand submits (legal_entity_verified etc.)
    -- Prompt 13's admin queue is where Teenure actually verifies these
    before manually_reviewed_at gets set (startup-validation path) or
    before an admin trusts them enough to let a campaign through
    moderation review at all. This endpoint alone does not grant
    eligibility for a brand that's lying on the form -- it only records
    the attestation the moderation queue then checks."""
    brand = await _get_own_brand_profile(conn, user)
    updated = await insight_feedback_repository.upsert_eligibility(
        conn, brand.id,
        legal_entity_verified=body.legal_entity_verified,
        named_contact_verified=body.named_contact_verified,
        business_presence_verified=body.business_presence_verified,
        funding_confirmed=body.funding_confirmed,
        content_agreement_signed=body.content_agreement_signed,
        is_early_stage_startup=body.is_early_stage_startup,
        incorporated_3mo_or_backed=body.incorporated_3mo_or_backed,
        has_real_product=body.has_real_product,
    )
    return _to_eligibility_response(updated)


def _to_insight_campaign_response(c: insight_feedback_repository.InsightCampaign) -> InsightCampaignResponse:
    return InsightCampaignResponse(
        id=c.id, title=c.title, material_url=c.material_url, business_question=c.business_question,
        feedback_format=c.feedback_format, qa_questions=c.qa_questions, panel_size=c.panel_size,
        panel_criteria=c.panel_criteria,
        compensation_cents=c.compensation_cents, confidentiality_terms=c.confidentiality_terms,
        is_startup_validation=c.is_startup_validation, moderation_status=c.moderation_status,
        rejection_reason=c.rejection_reason, status=c.status, created_at=c.created_at,
    )


async def _require_owned_insight_campaign(
    conn: asyncpg.Connection, campaign_id: str, brand_id: str
) -> insight_feedback_repository.InsightCampaign:
    campaign = await insight_feedback_repository.get_by_id_and_brand(conn, campaign_id, brand_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "insight_campaign_not_found", "message": "No campaign found for that id."},
        )
    return campaign


@brands_insight_router.post("/campaigns", response_model=InsightCampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_insight_campaign(
    body: InsightCampaignCreateRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InsightCampaignResponse:
    brand = await _get_own_brand_profile(conn, user)
    _require_company_profile_complete(brand)
    try:
        await insight_feedback_service.require_eligible_brand(conn, brand.id)
    except insight_feedback_service.InsightNotEligibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "not_vetted", "message": exc.message}
        ) from exc
    campaign = await insight_feedback_repository.create_campaign(
        conn, brand_id=brand.id, title=body.title, material_url=body.material_url,
        business_question=body.business_question, panel_size=body.panel_size,
        panel_criteria=body.panel_criteria, compensation_cents=body.compensation_cents,
        confidentiality_terms=body.confidentiality_terms, is_startup_validation=body.is_startup_validation,
        opens_at=body.opens_at, closes_at=body.closes_at,
        feedback_format=body.feedback_format, qa_questions=[q.model_dump() for q in body.qa_questions],
    )
    return _to_insight_campaign_response(campaign)


@brands_insight_router.get("/campaigns", response_model=list[InsightCampaignResponse])
async def list_own_insight_campaigns(
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[InsightCampaignResponse]:
    brand = await _get_own_brand_profile(conn, user)
    rows = await insight_feedback_repository.list_for_brand(conn, brand.id)
    return [_to_insight_campaign_response(c) for c in rows]


@brands_insight_router.post("/campaigns/{campaign_id}/submit-for-review", response_model=InsightCampaignResponse)
async def submit_insight_campaign_for_review(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InsightCampaignResponse:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_insight_campaign(conn, campaign_id, brand.id)
    updated = await insight_feedback_repository.submit_for_review(conn, campaign_id)
    return _to_insight_campaign_response(updated)


@brands_insight_router.post("/campaigns/{campaign_id}/activate", response_model=InsightCampaignResponse)
async def activate_insight_campaign(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InsightCampaignResponse:
    brand = await _get_own_brand_profile(conn, user)
    campaign = await _require_owned_insight_campaign(conn, campaign_id, brand.id)
    if campaign.moderation_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "not_approved", "message": "This campaign has not been approved by Teenure review yet."},
        )
    try:
        updated = await insight_feedback_service.activate_with_panel(conn, campaign)
    except insight_feedback_service.InsufficientPanelError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "insufficient_panel",
                "message": f"Only {exc.available} opted-in talents match this campaign's criteria; {exc.needed} needed.",
            },
        ) from exc
    return _to_insight_campaign_response(updated)


@brands_insight_router.get("/campaigns/{campaign_id}/results", response_model=InsightBrandResultsResponse)
async def insight_campaign_results(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InsightBrandResultsResponse:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_insight_campaign(conn, campaign_id, brand.id)
    results = await insight_feedback_repository.brand_facing_results(conn, campaign_id)
    return InsightBrandResultsResponse(
        feedback_format=results["feedback_format"],
        released=results["released"],
        responses_submitted=results["responses_submitted"],
        responses_required=results["responses_required"],
        results=[InsightBrandResultResponse(**r) for r in results["results"]],
    )


# ══════════════════════════════════════════════════════════════════
# /talents/insight -- opt-in, invitations, responses
# ══════════════════════════════════════════════════════════════════


@talents_insight_router.get("/opt-in")
async def get_insight_opt_in(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> dict:
    profile = await _get_own_talent_profile(conn, user)
    opted_in = await talent_profiles_repository.get_insight_feedback_opt_in(conn, profile.id)
    return {"opted_in": opted_in}


@talents_insight_router.put("/opt-in")
async def set_insight_opt_in(
    opted_in: bool,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> dict:
    profile = await _get_own_talent_profile(conn, user)
    await talent_profiles_repository.set_insight_feedback_opt_in(conn, profile.id, opted_in=opted_in)
    if opted_in:
        # Provision the handle at the moment of opt-in, not lazily on
        # first panel selection -- a talent should be able to see their
        # handle before it's ever used anywhere (issue #37).
        await pseudonym_service.get_or_create_pseudonym(conn, profile.id)
    return {"opted_in": opted_in}


@talents_insight_router.get("/invitations", response_model=list[InsightInvitationResponse])
async def my_insight_invitations(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[InsightInvitationResponse]:
    profile = await _get_own_talent_profile(conn, user)
    rows = await insight_feedback_repository.list_invitations_for_talent(conn, profile.id)
    return [
        InsightInvitationResponse(
            panel_member_id=i.panel_member_id, campaign_id=i.campaign_id, campaign_title=i.campaign_title,
            business_question=i.business_question, feedback_format=i.feedback_format,
            qa_questions=i.qa_questions, confidentiality_terms=i.confidentiality_terms,
            compensation_cents=i.compensation_cents, invited_at=i.invited_at, responded_at=i.responded_at,
        )
        for i in rows
    ]


@talents_insight_router.post("/invitations/{panel_member_id}/respond", response_model=InsightResponseAck)
async def respond_to_insight_invitation(
    panel_member_id: str,
    body: InsightResponseSubmitRequest,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InsightResponseAck:
    profile = await _get_own_talent_profile(conn, user)
    member = await insight_feedback_repository.get_panel_member_for_talent(conn, panel_member_id, profile.id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "invitation_not_found", "message": "No panel invitation found for that id."},
        )
    if await insight_feedback_repository.has_responded(conn, panel_member_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "already_responded", "message": "You've already submitted feedback for this invitation."},
        )
    campaign = await insight_feedback_repository.get_by_id(conn, str(member["campaign_id"]))

    if campaign.feedback_format == "rating_scale":
        if not body.ratings:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "wrong_format", "message": "This invitation expects ratings, not qa_answers."},
            )
        submitted_at = await insight_feedback_repository.submit_response(
            conn, panel_member_id=panel_member_id, feedback_format="rating_scale",
            ratings=[r.model_dump() for r in body.ratings],
        )
    else:
        if not body.qa_answers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "wrong_format", "message": "This invitation expects qa_answers, not ratings."},
            )
        try:
            submitted_at = await insight_feedback_service.submit_structured_qa_response(
                conn, panel_member_id=panel_member_id, campaign=campaign,
                qa_answers=[a.model_dump() for a in body.qa_answers],
            )
        except insight_feedback_service.UnknownQuestionIdError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "unknown_question_id", "message": str(exc)},
            ) from exc

    await insight_feedback_repository.mark_responded(conn, panel_member_id)
    return InsightResponseAck(panel_member_id=panel_member_id, submitted_at=submitted_at)
