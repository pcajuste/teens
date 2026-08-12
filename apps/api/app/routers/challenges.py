"""Skill Challenges backend (Build Prompt 8G): an open, low-commitment
submission surface distinct from campaigns -- unpaid, no FTC
disclosure, no parent-approval gate (see Teenure_Build_Prompts.md's
"THE FUNDAMENTAL DISTINCTION FROM CAMPAIGNS" for the full rationale).
Two routers, matching reps.py's split: brand-side CRUD/review lives on
`/brands/challenges/...`, rep-side discovery/submission on
`/reps/challenges/...` -- both included from app/main.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.security import AuthenticatedUser, require_role
from app.db.pool import get_connection
from app.repositories import (
    brand_profiles_repository,
    campaign_reps_repository,
    campaigns_repository,
    challenges_repository,
    rep_profiles_repository,
    users_repository,
)
from app.schemas.challenges import (
    ChallengeCreateRequest,
    ChallengeResponse,
    ChallengeSubmissionRepCardResponse,
    BrandSubmissionResponse,
    ConvertSubmissionRequest,
    ConvertSubmissionResponse,
    RepChallengeAvailableResponse,
    RepChallengeSubmissionResponse,
    RepChallengeSubmittedResponse,
    ReviewSubmissionRequest,
    SubmitChallengeRequest,
)
from app.services import payout_service
from app.services.email_service import send_challenge_converted_email
from app.services.parent_service import determine_parent_approval, send_campaign_approval_request
from app.services.resend_client import ResendClient, resend_client_dependency

brands_challenges_router = APIRouter(prefix="/brands/challenges", tags=["challenges"])
reps_challenges_router = APIRouter(prefix="/reps/challenges", tags=["challenges"])

STANDARD_INVITE_WINDOW_HOURS = 48


def _conversion_rate(submissions_count: int, conversion_count: int) -> float | None:
    if not submissions_count:
        return None
    return round(conversion_count / submissions_count, 2)


def _to_challenge_response(c: challenges_repository.Challenge) -> ChallengeResponse:
    return ChallengeResponse(
        id=c.id,
        brand_id=c.brand_id,
        title=c.title,
        brief=c.brief,
        category=c.category,
        target_cities=c.target_cities,
        submission_format=c.submission_format,
        submission_prompt=c.submission_prompt,
        status=c.status,
        max_submissions=c.max_submissions,
        submissions_count=c.submissions_count,
        conversion_count=c.conversion_count,
        conversion_rate=_conversion_rate(c.submissions_count, c.conversion_count),
        opens_at=c.opens_at,
        closes_at=c.closes_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


async def _get_own_brand_profile(conn: asyncpg.Connection, user: AuthenticatedUser) -> brand_profiles_repository.BrandProfile:
    profile = await brand_profiles_repository.get_by_user_id(conn, user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "brand_profile_not_found", "message": "Complete onboarding via PUT /brands/me first."},
        )
    return profile


async def _require_owned_challenge(conn: asyncpg.Connection, challenge_id: str, brand_id: str) -> challenges_repository.Challenge:
    challenge = await challenges_repository.get_by_id_and_brand(conn, challenge_id, brand_id)
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "challenge_not_found", "message": "No challenge found for that id."},
        )
    return challenge


# ══════════════════════════════════════════════════════════════════
# /brands/challenges -- brand CRUD (deliverable 2)
# ══════════════════════════════════════════════════════════════════


@brands_challenges_router.post("", response_model=ChallengeResponse, status_code=status.HTTP_201_CREATED)
async def create_challenge(
    body: ChallengeCreateRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ChallengeResponse:
    brand = await _get_own_brand_profile(conn, user)
    created = await challenges_repository.create_challenge(
        conn,
        brand_id=brand.id,
        title=body.title,
        brief=body.brief,
        category=body.category,
        target_cities=body.target_cities,
        submission_format=body.submission_format,
        submission_prompt=body.submission_prompt,
        max_submissions=body.max_submissions,
        opens_at=body.opens_at,
        closes_at=body.closes_at,
    )
    return _to_challenge_response(created)


@brands_challenges_router.get("", response_model=list[ChallengeResponse])
async def list_challenges(
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[ChallengeResponse]:
    brand = await _get_own_brand_profile(conn, user)
    rows = await challenges_repository.list_for_brand(conn, brand.id)
    return [_to_challenge_response(c) for c in rows]


@brands_challenges_router.put("/{challenge_id}", response_model=ChallengeResponse)
async def update_challenge(
    challenge_id: str,
    body: ChallengeCreateRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ChallengeResponse:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_challenge(conn, challenge_id, brand.id)  # 404 if not owned, regardless of status
    updated = await challenges_repository.update_challenge(
        conn,
        challenge_id,
        brand.id,
        title=body.title,
        brief=body.brief,
        category=body.category,
        target_cities=body.target_cities,
        submission_format=body.submission_format,
        submission_prompt=body.submission_prompt,
        max_submissions=body.max_submissions,
        opens_at=body.opens_at,
        closes_at=body.closes_at,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "challenge_not_editable",
                "message": "Active challenges cannot be edited. Close this challenge and create a new one.",
            },
        )
    return _to_challenge_response(updated)


@brands_challenges_router.post("/{challenge_id}/activate", response_model=ChallengeResponse)
async def activate_challenge(
    challenge_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ChallengeResponse:
    """Challenges are free for brands at launch -- no Stripe charge.
    Deliberate: challenges are a brand acquisition tool, and charging at
    launch would reduce adoption. Pricing is introduced later, once
    value is demonstrated."""
    brand = await _get_own_brand_profile(conn, user)
    challenge = await _require_owned_challenge(conn, challenge_id, brand.id)
    if challenge.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot activate from status '{challenge.status}'."},
        )
    if not challenge.title or not challenge.brief or not challenge.category or not challenge.submission_prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "incomplete_challenge", "message": "title, brief, category, and submission_prompt are all required to activate."},
        )
    updated = await challenges_repository.activate(conn, challenge_id, brand.id, opens_at=datetime.now(timezone.utc))
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": "Challenge status changed before activation completed."},
        )
    return _to_challenge_response(updated)


@brands_challenges_router.post("/{challenge_id}/close", response_model=ChallengeResponse)
async def close_challenge(
    challenge_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ChallengeResponse:
    """Idempotent -- closing an already-closed challenge returns the
    current state with a 200, not a 409 (spec deliverable 2)."""
    brand = await _get_own_brand_profile(conn, user)
    challenge = await _require_owned_challenge(conn, challenge_id, brand.id)
    updated = await challenges_repository.close(conn, challenge_id, brand.id)
    return _to_challenge_response(updated or challenge)


def _to_rep_card_response(card: challenges_repository.ChallengeSubmissionRepCard) -> ChallengeSubmissionRepCardResponse:
    return ChallengeSubmissionRepCardResponse(
        rep_id=card.rep_id,
        display_name=card.display_name,
        city=card.city,
        categories=card.categories,
        profile_completeness_score=card.profile_completeness_score,
        campaigns_completed=card.campaigns_completed,
        average_rating=card.average_rating,
        challenges_converted_count=card.challenges_converted_count,
        challenge_conversion_rate=card.challenge_conversion_rate,
    )


def _brand_facing_status(s: str) -> str:
    """Spec deliverable 2: 'declined' never appears in the brand's list
    view -- "the decline was their action," so it's shown back to them
    as 'reviewed' rather than surfacing the same word twice with two
    different meanings."""
    return "reviewed" if s == "declined" else s


@brands_challenges_router.get("/{challenge_id}/submissions", response_model=list[BrandSubmissionResponse])
async def list_submissions(
    challenge_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[BrandSubmissionResponse]:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_challenge(conn, challenge_id, brand.id)
    rows = await challenges_repository.list_for_challenge(conn, challenge_id)
    result: list[BrandSubmissionResponse] = []
    for s in rows:
        card = await challenges_repository.get_submission_rep_card(conn, s.rep_id)
        if card is None:
            continue
        result.append(
            BrandSubmissionResponse(
                id=s.id,
                challenge_id=s.challenge_id,
                rep=_to_rep_card_response(card),
                submission_text=s.submission_text,
                submission_file_urls=s.submission_file_urls,
                status=_brand_facing_status(s.status),
                brand_note=s.brand_note,
                submitted_at=s.submitted_at,
                converted_to_campaign_id=s.converted_to_campaign_id,
                payout_cents=s.payout_cents,
                payout_status=s.payout_status,
            )
        )
    return result


async def _require_owned_submission(
    conn: asyncpg.Connection, challenge_id: str, submission_id: str, brand_id: str
) -> tuple[challenges_repository.Challenge, challenges_repository.ChallengeSubmission]:
    challenge = await _require_owned_challenge(conn, challenge_id, brand_id)
    submission = await challenges_repository.get_by_id_and_challenge(conn, submission_id, challenge_id)
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "submission_not_found", "message": "No submission found for that id on this challenge."},
        )
    return challenge, submission


@brands_challenges_router.post("/{challenge_id}/submissions/{submission_id}/review", response_model=BrandSubmissionResponse)
async def review_submission(
    challenge_id: str,
    submission_id: str,
    body: ReviewSubmissionRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> BrandSubmissionResponse:
    brand = await _get_own_brand_profile(conn, user)
    challenge, submission = await _require_owned_submission(conn, challenge_id, submission_id, brand.id)
    updated = await challenges_repository.mark_reviewed(conn, submission_id, brand_note=body.brand_note, at=datetime.now(timezone.utc))
    final = updated or submission  # idempotent -- already-reviewed is not an error
    card = await challenges_repository.get_submission_rep_card(conn, final.rep_id)
    return BrandSubmissionResponse(
        id=final.id,
        challenge_id=final.challenge_id,
        rep=_to_rep_card_response(card) if card else _to_rep_card_response(
            challenges_repository.ChallengeSubmissionRepCard(
                rep_id=final.rep_id, display_name="", city="", categories=[], profile_completeness_score=0,
                campaigns_completed=0, average_rating=None, challenges_converted_count=0, challenge_conversion_rate=None,
            )
        ),
        submission_text=final.submission_text,
        submission_file_urls=final.submission_file_urls,
        status=_brand_facing_status(final.status),
        brand_note=final.brand_note,
        submitted_at=final.submitted_at,
        converted_to_campaign_id=final.converted_to_campaign_id,
        payout_cents=final.payout_cents,
        payout_status=final.payout_status,
    )


@brands_challenges_router.post("/{challenge_id}/submissions/{submission_id}/convert", response_model=ConvertSubmissionResponse)
async def convert_submission(
    challenge_id: str,
    submission_id: str,
    body: ConvertSubmissionRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(resend_client_dependency),
) -> ConvertSubmissionResponse:
    """The key action (spec deliverable 3). Steps a-k execute atomically
    in one DB transaction -- a partially-converted submission is worse
    than a failed conversion. Idempotent: a submission already
    'converted' is not re-processed -- the second call returns the
    current converted state with 200, never a 500 or a duplicate
    payout/campaign_reps row."""
    brand = await _get_own_brand_profile(conn, user)
    challenge, submission = await _require_owned_submission(conn, challenge_id, submission_id, brand.id)

    if submission.status == "converted":
        # Idempotent replay -- return current state without touching
        # anything again (no second campaign_reps row, no second
        # Transfer). release_challenge_conversion_bonus below is itself
        # idempotent too, so calling it again here is also safe, but
        # short-circuiting avoids the extra campaign lookup/email noise
        # on a pure replay.
        return ConvertSubmissionResponse(
            id=submission.id,
            status="converted",
            converted_to_campaign_id=submission.converted_to_campaign_id,
            payout_cents=submission.payout_cents,
            payout_status=submission.payout_status,
            stripe_transfer_id=submission.stripe_transfer_id,
        )
    if submission.status not in ("submitted", "reviewed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot convert from status '{submission.status}'."},
        )

    campaign = await campaigns_repository.get_by_id_and_brand(conn, body.campaign_id, brand.id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_not_found", "message": "No campaign found for that id on this brand."},
        )
    if campaign.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "campaign_not_active", "message": "Only an active campaign can receive a challenge conversion invitation."},
        )

    existing_invite = await campaign_reps_repository.get_for_rep_and_campaign(conn, submission.rep_id, campaign.id)
    if existing_invite is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "already_invited", "message": "This rep already has a campaign_reps row on that campaign."},
        )

    current_count = await campaign_reps_repository.count_non_declined_for_campaign(conn, campaign.id)
    if current_count >= campaign.max_reps:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "campaign_full", "message": "This campaign has no available rep slots."},
        )

    payout_cents = settings.challenge_conversion_bonus_cents
    parent_approval_status, parent_approval_deadline = await determine_parent_approval(conn, submission.rep_id)

    async with conn.transaction():
        # (c) Create the campaign_reps invitation -- identical in
        # structure to a direct brand invitation (Prompt 8's
        # create_invite), so it's indistinguishable from that path
        # anywhere downstream (RLS, payout engine, campaign lifecycle).
        # Still runs through the normal under-16 parent-approval gate --
        # this is a real paid campaign invitation, unlike the challenge
        # submission itself.
        invite = await campaign_reps_repository.create_invite(
            conn,
            campaign_id=campaign.id,
            rep_id=submission.rep_id,
            parent_approval_status=parent_approval_status,
            parent_approval_deadline=parent_approval_deadline,
        )
        # (d)-(g) Mark the submission converted.
        updated_submission = await challenges_repository.mark_converted(
            conn, submission_id, converted_to_campaign_id=campaign.id, payout_cents=payout_cents, at=datetime.now(timezone.utc)
        )
        if updated_submission is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "illegal_transition", "message": "Submission status changed before conversion completed."},
            )
        # (i)-(j) Update aggregate counters.
        await challenges_repository.increment_conversion_count(conn, challenge_id)
        await rep_profiles_repository.increment_challenges_converted_count(conn, submission.rep_id)

    if parent_approval_status == "pending":
        await send_campaign_approval_request(conn, resend_client, rep_id=submission.rep_id, campaign_id=campaign.id)

    # (h) Release the conversion bonus -- outside the transaction (a
    # Stripe API call has no business holding a DB transaction open),
    # same convention as every other confirm-then-release pairing in
    # this codebase (app/routers/brands.py's confirm_submission,
    # confirm_milestone).
    result = await payout_service.release_challenge_conversion_bonus(conn, settings, submission_id)

    # (k) Notify the rep -- bonus amount formatted from config, never
    # hardcoded.
    rep = await rep_profiles_repository.get_by_id(conn, submission.rep_id)
    if rep is not None:
        rep_user = await users_repository.get_user_by_id(conn, rep.user_id)
        if rep_user is not None:
            await send_challenge_converted_email(
                rep_user.email, campaign_title=campaign.title, bonus_cents=payout_cents, client=resend_client
            )

    final = await challenges_repository.get_submission_by_id(conn, submission_id)
    return ConvertSubmissionResponse(
        id=final.id,
        status="converted",
        converted_to_campaign_id=final.converted_to_campaign_id,
        payout_cents=final.payout_cents,
        payout_status=final.payout_status,
        stripe_transfer_id=result.stripe_transfer_id or final.stripe_transfer_id,
    )


@brands_challenges_router.post("/{challenge_id}/submissions/{submission_id}/decline", response_model=BrandSubmissionResponse)
async def decline_submission(
    challenge_id: str,
    submission_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> BrandSubmissionResponse:
    """Idempotent. No rep notification -- declined submissions are
    silently archived (spec deliverable 3: protects rep confidence,
    especially for younger users)."""
    brand = await _get_own_brand_profile(conn, user)
    challenge, submission = await _require_owned_submission(conn, challenge_id, submission_id, brand.id)
    updated = await challenges_repository.mark_declined(conn, submission_id)
    final = updated or submission
    card = await challenges_repository.get_submission_rep_card(conn, final.rep_id)
    return BrandSubmissionResponse(
        id=final.id,
        challenge_id=final.challenge_id,
        rep=_to_rep_card_response(card) if card else _to_rep_card_response(
            challenges_repository.ChallengeSubmissionRepCard(
                rep_id=final.rep_id, display_name="", city="", categories=[], profile_completeness_score=0,
                campaigns_completed=0, average_rating=None, challenges_converted_count=0, challenge_conversion_rate=None,
            )
        ),
        submission_text=final.submission_text,
        submission_file_urls=final.submission_file_urls,
        status=_brand_facing_status(final.status),
        brand_note=final.brand_note,
        submitted_at=final.submitted_at,
        converted_to_campaign_id=final.converted_to_campaign_id,
        payout_cents=final.payout_cents,
        payout_status=final.payout_status,
    )


# ══════════════════════════════════════════════════════════════════
# /reps/challenges -- rep discovery + submission (deliverable 4)
# ══════════════════════════════════════════════════════════════════


async def _get_own_rep_profile(conn: asyncpg.Connection, user: AuthenticatedUser) -> rep_profiles_repository.RepProfile:
    profile = await rep_profiles_repository.get_by_user_id(conn, user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "rep_profile_not_found", "message": "Complete onboarding via PUT /reps/me first."},
        )
    return profile


@reps_challenges_router.get("/available", response_model=list[RepChallengeAvailableResponse])
async def available_challenges(
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[RepChallengeAvailableResponse]:
    """No parent values_filter is applied here -- challenges are unpaid,
    involve no brand relationship, and require no parent approval
    (spec deliverable 4's explicit instruction). This is a deliberate
    scope decision, distinct from GET /reps/campaigns/available's own
    apply_values_filter loop: a rep under 16 whose parent has
    campaign_approval_required=TRUE still sees every matching challenge
    -- that gate is specific to paid campaigns, not to challenges, which
    involve no financial transaction with a minor at submission time."""
    profile = await _get_own_rep_profile(conn, user)
    rows = await challenges_repository.list_available_for_rep(
        conn, rep_id=profile.id, categories=profile.categories, city=profile.city
    )
    return [
        RepChallengeAvailableResponse(
            id=c.id,
            title=c.title,
            brief=c.brief,
            category=c.category,
            submission_format=c.submission_format,
            submission_prompt=c.submission_prompt,
            target_cities=c.target_cities,
            closes_at=c.closes_at,
        )
        for c in rows
    ]


@reps_challenges_router.get("/submitted", response_model=list[RepChallengeSubmittedResponse])
async def submitted_challenges(
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[RepChallengeSubmittedResponse]:
    """Status remap per spec deliverable 4: 'submitted'/'reviewed' both
    surface as 'submitted' (a rep never learns whether a brand has
    looked yet); 'declined' rows are excluded entirely -- never
    returned by this endpoint under any circumstances."""
    profile = await _get_own_rep_profile(conn, user)
    rows = await challenges_repository.list_for_rep(conn, profile.id)
    result: list[RepChallengeSubmittedResponse] = []
    for s in rows:
        if s.status == "declined":
            continue
        challenge = await challenges_repository.get_by_id(conn, s.challenge_id)
        if challenge is None:
            continue
        if s.status == "converted":
            campaign = await campaigns_repository.get_by_id(conn, s.converted_to_campaign_id) if s.converted_to_campaign_id else None
            result.append(
                RepChallengeSubmittedResponse(
                    challenge_id=s.challenge_id,
                    challenge_title=challenge.title,
                    category=challenge.category,
                    submitted_at=s.submitted_at,
                    status="converted",
                    campaign_id=campaign.id if campaign else None,
                    campaign_title=campaign.title if campaign else None,
                    payout_per_rep_cents=campaign.payout_per_rep_cents if campaign else None,
                    bonus_cents=s.payout_cents,
                )
            )
        else:
            result.append(
                RepChallengeSubmittedResponse(
                    challenge_id=s.challenge_id,
                    challenge_title=challenge.title,
                    category=challenge.category,
                    submitted_at=s.submitted_at,
                    status="submitted",
                )
            )
    return result


@reps_challenges_router.post("/{challenge_id}/submit", response_model=RepChallengeSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_challenge(
    challenge_id: str,
    body: SubmitChallengeRequest,
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> RepChallengeSubmissionResponse:
    profile = await _get_own_rep_profile(conn, user)
    challenge = await challenges_repository.get_by_id(conn, challenge_id)
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "challenge_not_found", "message": "No challenge found for that id."},
        )
    if challenge.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "challenge_closed", "message": "This challenge is closed and no longer accepting submissions."},
        )
    if challenge.max_submissions is not None and challenge.submissions_count >= challenge.max_submissions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "challenge_full", "message": "This challenge has reached its maximum number of submissions."},
        )

    existing = await challenges_repository.get_for_rep_and_challenge(conn, profile.id, challenge_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "already_submitted", "message": "You have already submitted to this challenge."},
        )

    if challenge.submission_format == "text" and not (body.submission_text and body.submission_text.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "submission_text_required", "message": "This challenge requires a text submission."},
        )
    if challenge.submission_format == "file" and not body.submission_file_urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "submission_file_required", "message": "This challenge requires at least one file submission."},
        )
    if challenge.submission_format == "both" and not (
        (body.submission_text and body.submission_text.strip()) or body.submission_file_urls
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "submission_required", "message": "This challenge requires a text and/or file submission."},
        )

    # Server-side enforcement of the pre-challenge disclosure (spec
    # deliverable 4e) -- a rep calling this endpoint via direct API,
    # without ever seeing the disclosure UI, must still acknowledge the
    # terms, or the submission is rejected. This is the technical gate,
    # not a UI hint, mirroring how FTC disclosure is enforced for
    # campaigns (app/routers/reps.py's submit_campaign).
    if not body.disclosure_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "disclosure_acknowledgment_required",
                "message": (
                    "Challenge disclosure acknowledgment required. Challenges are unpaid brand "
                    "discovery tools. Your submission may result in a paid campaign invitation, "
                    "but this is not guaranteed."
                ),
            },
        )

    async with conn.transaction():
        created = await challenges_repository.create_submission(
            conn,
            challenge_id=challenge_id,
            rep_id=profile.id,
            submission_text=body.submission_text,
            submission_file_urls=body.submission_file_urls,
        )
        await challenges_repository.increment_submissions_count(conn, challenge_id)
        await rep_profiles_repository.increment_challenges_submitted_count(conn, profile.id)

    # Neutral confirmation only -- no estimated response time, no
    # implication the brand will respond (spec deliverable 4i).
    return RepChallengeSubmissionResponse(id=created.id, challenge_id=created.challenge_id, status="submitted", submitted_at=created.submitted_at)
