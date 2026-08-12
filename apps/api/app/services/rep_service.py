"""Rep profile + campaign-participation state machine (Prompt 5).

Section 8's Rep Routes + Campaign participation routes, and Section 5
Phase 1's feature set, implemented against the schema from Section 7
plus the invite_expires_at addition from migration 0006.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg

from app.core.constants import INVITE_EXPIRY_HOURS

# ── Errors ──────────────────────────────────────────────────────────


class RepProfileNotFoundError(Exception):
    pass


class CampaignNotFoundError(Exception):
    pass


class CampaignNotEligibleError(Exception):
    """Campaign isn't open, or doesn't target this rep's category/city."""


class AlreadyAppliedError(Exception):
    pass


class InviteNotFoundError(Exception):
    """No campaign_reps row for this rep on this campaign."""


class IllegalTransitionError(Exception):
    """409 -- the requested action isn't valid from the row's current status."""


class FtcDisclosureRequiredError(Exception):
    pass


class AwaitingParentApprovalError(Exception):
    """403 -- distinct from a generic IllegalTransitionError (Prompt 4A
    retrofit, deliverable 9)."""


# ── Profile ─────────────────────────────────────────────────────────

_UPDATABLE_FIELDS = (
    "display_name", "school_name", "school_type", "city", "state",
    "graduation_year", "bio", "categories", "instagram_handle",
    "tiktok_handle", "recruiter_visible",
)


def get_rep_profile_by_user_id(conn: psycopg.Connection, user_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM public.rep_profiles WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
    if row is None:
        raise RepProfileNotFoundError(user_id)
    return row


def compute_completeness_score(profile: dict) -> int:
    """0-100. Each of 8 fields Section 5's Dashboard cares about is worth
    12.5 points (rounded down, capped at 100) -- deliberately simple/
    explicit per deliverable 9's requirement to state the rule, not
    just implement one.
    """
    checks = [
        bool(profile.get("display_name")),
        bool(profile.get("school_name")),
        bool(profile.get("city")) and bool(profile.get("state")),
        bool(profile.get("graduation_year")),
        bool(profile.get("bio")),
        bool(profile.get("categories")),
        bool(profile.get("instagram_handle")) or bool(profile.get("tiktok_handle")),
        profile.get("total_campaigns_completed", 0) > 0,
    ]
    return min(100, int(sum(checks) * (100 / len(checks))))


def update_rep_profile(conn: psycopg.Connection, user_id: str, updates: dict) -> dict:
    profile = get_rep_profile_by_user_id(conn, user_id)
    fields = {k: v for k, v in updates.items() if k in _UPDATABLE_FIELDS and v is not None}

    merged = {**profile, **fields}
    new_score = compute_completeness_score(merged)

    set_clauses = [f"{field} = %s" for field in fields]
    params: list = list(fields.values())
    set_clauses.append("profile_completeness_score = %s")
    params.append(new_score)
    set_clauses.append("updated_at = now()")
    params.append(profile["id"])

    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE public.rep_profiles SET {', '.join(set_clauses)} WHERE id = %s RETURNING *",
            params,
        )
        row = cur.fetchone()
    conn.commit()
    return row


def profile_preview(profile: dict) -> dict:
    return {
        "display_name": profile["display_name"],
        "school_name": profile["school_name"],
        "city": profile["city"],
        "state": profile["state"],
        "graduation_year": profile["graduation_year"],
        "bio": profile["bio"],
        "categories": profile["categories"],
        "instagram_handle": profile["instagram_handle"],
        "tiktok_handle": profile["tiktok_handle"],
        "total_campaigns_completed": profile["total_campaigns_completed"],
        "average_rating": profile["average_rating"],
    }


# ── Campaign browsing ───────────────────────────────────────────────


def _parent_values_filters(conn: psycopg.Connection, rep_id: str) -> list[str]:
    """Section 9A / Prompt 4A retrofit (deliverable 9): a rep's parent
    (if any parent_records row exists for them) can block whole campaign
    categories. Applied here, server-side, as the actual enforcement
    point -- the rep never sees a blocked-category campaign as an
    option in the first place.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT values_filters FROM public.parent_records WHERE rep_id = %s",
            (rep_id,),
        )
        row = cur.fetchone()
    return row["values_filters"] if row else []


def campaigns_available(conn: psycopg.Connection, rep: dict) -> list[dict]:
    blocked_categories = _parent_values_filters(conn, rep["id"])
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.* FROM public.campaigns c
            WHERE c.status = 'active'
              AND c.target_categories && %(categories)s
              AND (c.target_cities = '{}' OR c.target_cities && ARRAY[%(city)s]::text[])
              AND NOT (c.target_categories && %(blocked)s)
              AND NOT EXISTS (
                SELECT 1 FROM public.campaign_reps cr
                WHERE cr.campaign_id = c.id AND cr.rep_id = %(rep_id)s
              )
            ORDER BY c.created_at DESC
            """,
            {
                "categories": rep["categories"],
                "city": rep["city"],
                "rep_id": rep["id"],
                "blocked": blocked_categories,
            },
        )
        return cur.fetchall()


def _campaigns_by_status(conn: psycopg.Connection, rep_id: str, statuses: tuple[str, ...]) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cr.id AS campaign_reps_id, cr.status, cr.payout_cents, cr.invite_expires_at,
                   cr.parent_approval_status,
                   c.id AS campaign_id, c.title, c.product_name, c.deliverables_description,
                   c.start_date, c.end_date
            FROM public.campaign_reps cr
            JOIN public.campaigns c ON c.id = cr.campaign_id
            WHERE cr.rep_id = %s AND cr.status = ANY(%s)
            ORDER BY cr.invited_at DESC
            """,
            (rep_id, list(statuses)),
        )
        return cur.fetchall()


def campaigns_active(conn: psycopg.Connection, rep_id: str) -> list[dict]:
    return _campaigns_by_status(conn, rep_id, ("invited", "accepted", "submitted", "revision_requested"))


def campaigns_history(conn: psycopg.Connection, rep_id: str) -> list[dict]:
    return _campaigns_by_status(conn, rep_id, ("confirmed", "paid", "declined"))


# ── Earnings ────────────────────────────────────────────────────────


def earnings_breakdown(conn: psycopg.Connection, rep_id: str) -> dict:
    """Buckets by campaign_reps.payout_status, not the cached
    rep_profiles.total_earnings_cents, per deliverable 5.

    pending    -> payout_status = 'pending'    (confirmed by brand, not yet initiated)
    confirmed  -> payout_status = 'processing' (Stripe transfer initiated, not yet settled)
    paid       -> payout_status = 'paid'
    lifetime   -> sum across all three (a 'failed' payout is excluded --
                  it isn't money the rep has or will imminently have)
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT payout_status, COALESCE(SUM(payout_cents), 0) AS total
            FROM public.campaign_reps
            WHERE rep_id = %s AND payout_cents IS NOT NULL
            GROUP BY payout_status
            """,
            (rep_id,),
        )
        rows = {r["payout_status"]: r["total"] for r in cur.fetchall()}

    pending = rows.get("pending", 0)
    confirmed = rows.get("processing", 0)
    paid = rows.get("paid", 0)
    return {
        "pending_cents": pending,
        "confirmed_cents": confirmed,
        "paid_cents": paid,
        "lifetime_total_cents": pending + confirmed + paid,
    }


# ── Campaign participation state machine ───────────────────────────


def _get_campaign(conn: psycopg.Connection, campaign_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM public.campaigns WHERE id = %s", (campaign_id,))
        row = cur.fetchone()
    if row is None:
        raise CampaignNotFoundError(campaign_id)
    return row


def _get_campaign_rep(conn: psycopg.Connection, campaign_id: str, rep_id: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM public.campaign_reps WHERE campaign_id = %s AND rep_id = %s",
            (campaign_id, rep_id),
        )
        return cur.fetchone()


def apply_to_campaign(conn: psycopg.Connection, rep: dict, campaign_id: str) -> dict:
    campaign = _get_campaign(conn, campaign_id)

    targets_category = bool(set(campaign["target_categories"]) & set(rep["categories"]))
    targets_city = not campaign["target_cities"] or rep["city"] in campaign["target_cities"]
    if campaign["status"] != "active" or not targets_category or not targets_city:
        raise CampaignNotEligibleError(
            "This campaign is not open, or doesn't match your categories/city"
        )

    if _get_campaign_rep(conn, campaign_id, rep["id"]) is not None:
        raise AlreadyAppliedError("You've already applied to or been invited to this campaign")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=INVITE_EXPIRY_HOURS)

    # Parent approval gate (Section 9A / Prompt 4A retrofit, deliverable
    # 9): mirrors the same 48h window as the rep's own accept/decline
    # deadline.
    with conn.cursor() as cur:
        cur.execute(
            "SELECT campaign_approval_required FROM public.parent_records WHERE rep_id = %s",
            (rep["id"],),
        )
        parent_row = cur.fetchone()
    if parent_row and parent_row["campaign_approval_required"]:
        parent_approval_status = "pending"
        parent_approval_deadline = expires_at
    else:
        parent_approval_status = "not_required"
        parent_approval_deadline = None

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.campaign_reps
                (campaign_id, rep_id, status, invited_at, invite_expires_at,
                 parent_approval_status, parent_approval_deadline)
            VALUES (%s, %s, 'invited', %s, %s, %s, %s)
            RETURNING *
            """,
            (campaign_id, rep["id"], now, expires_at, parent_approval_status, parent_approval_deadline),
        )
        row = cur.fetchone()
    conn.commit()
    return row


def accept_invite(conn: psycopg.Connection, rep_id: str, campaign_id: str, ftc_disclosure_accepted: bool) -> dict:
    cr = _get_campaign_rep(conn, campaign_id, rep_id)
    if cr is None:
        raise InviteNotFoundError(campaign_id)
    if cr["status"] != "invited":
        raise IllegalTransitionError(f"Cannot accept an invite in status '{cr['status']}'")
    if cr["invite_expires_at"] is not None and datetime.now(timezone.utc) > cr["invite_expires_at"]:
        raise IllegalTransitionError("This invite has expired")
    if cr.get("parent_approval_status") == "pending":
        raise AwaitingParentApprovalError(
            "This campaign is awaiting parent approval before you can accept it"
        )
    if not ftc_disclosure_accepted:
        raise FtcDisclosureRequiredError(
            "You must accept the FTC sponsorship disclosure before accepting a campaign"
        )

    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.campaign_reps
            SET status = 'accepted', accepted_at = %s,
                ftc_disclosure_accepted = TRUE, ftc_accepted_at = %s
            WHERE id = %s
            RETURNING *
            """,
            (now, now, cr["id"]),
        )
        row = cur.fetchone()
        cur.execute(
            "UPDATE public.campaigns SET reps_accepted_count = reps_accepted_count + 1 WHERE id = %s",
            (campaign_id,),
        )
    conn.commit()
    return row


def decline_invite(conn: psycopg.Connection, rep_id: str, campaign_id: str) -> dict:
    cr = _get_campaign_rep(conn, campaign_id, rep_id)
    if cr is None:
        raise InviteNotFoundError(campaign_id)
    if cr["status"] != "invited":
        raise IllegalTransitionError(f"Cannot decline an invite in status '{cr['status']}'")

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE public.campaign_reps SET status = 'declined' WHERE id = %s RETURNING *",
            (cr["id"],),
        )
        row = cur.fetchone()
    conn.commit()
    return row


_WITHDRAWABLE_STATUSES = ("invited", "accepted", "submitted", "revision_requested")


def withdraw_campaign(conn: psycopg.Connection, rep_id: str, campaign_id: str) -> dict:
    """One-tap withdrawal (Prompt 5 deliverable 9 / Prompt 4A retrofit
    deliverable 9): no penalty, no explanation required. Available at
    any status where withdrawing is still meaningful -- not once the
    campaign has already been confirmed/paid (payout protection for work
    already submitted and confirmed: withdrawing doesn't claw back a
    payout that has already been finalized).
    """
    cr = _get_campaign_rep(conn, campaign_id, rep_id)
    if cr is None:
        raise InviteNotFoundError(campaign_id)
    previous_status = cr["status"]
    if previous_status not in _WITHDRAWABLE_STATUSES:
        raise IllegalTransitionError(f"Cannot withdraw from status '{previous_status}'")

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE public.campaign_reps SET status = 'declined' WHERE id = %s RETURNING *",
            (cr["id"],),
        )
        row = cur.fetchone()
        if previous_status == "accepted":
            cur.execute(
                "UPDATE public.campaigns SET reps_accepted_count = GREATEST(0, reps_accepted_count - 1) WHERE id = %s",
                (campaign_id,),
            )
    conn.commit()
    return row


def submit_campaign(
    conn: psycopg.Connection, rep_id: str, campaign_id: str, *, submission_text: str, submission_file_urls: list[str]
) -> dict:
    cr = _get_campaign_rep(conn, campaign_id, rep_id)
    if cr is None:
        raise InviteNotFoundError(campaign_id)
    if cr["status"] not in ("accepted", "revision_requested"):
        raise IllegalTransitionError(f"Cannot submit from status '{cr['status']}'")
    if not cr["ftc_disclosure_accepted"]:
        raise FtcDisclosureRequiredError(
            "FTC sponsorship disclosure must be accepted before submitting"
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.campaign_reps
            SET status = 'submitted', submission_text = %s, submission_file_urls = %s, submitted_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (submission_text, submission_file_urls, cr["id"]),
        )
        row = cur.fetchone()
    conn.commit()
    return row


# ── Scheduled job (registered in app.jobs.runner) ───────────────────


def expire_stale_invites(conn: psycopg.Connection) -> int:
    """Auto-decline 'invited' rows past their invite_expires_at.

    Frees the campaign's rep slot for other reps -- no reps_accepted_count
    change needed since an expired invite was never counted as accepted.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.campaign_reps
            SET status = 'declined'
            WHERE status = 'invited' AND invite_expires_at < now()
            RETURNING id
            """,
        )
        expired = cur.fetchall()
    conn.commit()
    return len(expired)


def expire_lapsed_parent_approvals(conn: psycopg.Connection) -> int:
    """Prompt 4A retrofit (deliverable 9): auto-decline invitations whose
    parent_approval_deadline has lapsed without a parent decision --
    same 48h window as the rep's own invite_expires_at, checked
    separately since a parent's non-response is a distinct failure mode
    from the rep's own non-response.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.campaign_reps
            SET status = 'declined', parent_approval_status = 'blocked', parent_decided_at = now()
            WHERE parent_approval_status = 'pending'
              AND status = 'invited'
              AND parent_approval_deadline < now()
            RETURNING id
            """,
        )
        expired = cur.fetchall()
    conn.commit()
    return len(expired)
