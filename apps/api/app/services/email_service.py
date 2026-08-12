"""Transactional email shell, sent via Resend.

Prompt 4 implements send_parental_consent_email; Prompt 4A adds the
parent-portal sends below. All go through
app/services/resend_client.py's injectable client (real HTTP in
production, an in-memory fake in dev/test -- see that module).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.resend_client import ResendClient

if TYPE_CHECKING:
    from app.repositories.campaign_reps_repository import PendingApproval


async def send_signup_verification_email(to: str, verification_link: str) -> None:
    """Prompt 4A+: post-signup email verification (not required by
    Prompt 4's signup flow, which activates 16+ reps immediately and
    gates under-16 reps on parental consent instead)."""
    raise NotImplementedError


async def send_parental_consent_email(parent_email: str, consent_link: str, client: ResendClient) -> None:
    """Double opt-in consent email to a parent. Plain language, no
    legalese: explains that their teen signed up for Teenure, what the
    platform does, and that the link expires in 72 hours."""
    html = f"""
    <p>Your teen has started signing up for Teenure, a platform where
    teens complete brand campaigns for pay and build a verified record
    of their work for college and job applications.</p>
    <p>Because they're under 16, we need your permission before their
    account can go live. You'll also get access to a parent portal
    where you can review and approve campaigns, filter out content
    categories you don't want them exposed to, and get a monthly
    summary of their activity.</p>
    <p><a href="{consent_link}">Review and give consent</a></p>
    <p>This link expires in 72 hours. If you didn't expect this email,
    you can safely ignore it -- no account will be activated without
    your consent.</p>
    """
    await client.send_email(
        to=parent_email,
        subject="Action needed: parental consent for Teenure",
        html=html,
    )


async def send_magic_link_email(parent_email: str, magic_link: str, client: ResendClient) -> None:
    """Parent-portal login link. Expires in 15 minutes -- shorter than
    the consent link, since this is a login mechanism a parent is
    expected to use right away, not a one-time signup step."""
    html = f"""
    <p>Here's your link to sign in to your Teenure parent portal.</p>
    <p><a href="{magic_link}">Sign in</a></p>
    <p>This link expires in 15 minutes and can only be used once. If
    you didn't request this, you can safely ignore it.</p>
    """
    await client.send_email(to=parent_email, subject="Your Teenure parent portal sign-in link", html=html)


async def send_campaign_approval_request_email(
    parent_email: str, brief: "PendingApproval", client: ResendClient
) -> None:
    html = f"""
    <p>Your teen has been invited to a Teenure campaign with
    {brief.brand_name} and it's waiting on your approval.</p>
    <p><strong>{brief.title}</strong> ({brief.product_name})</p>
    <p>{brief.campaign_goal}</p>
    <p>Review the full details and approve or block it in your parent
    portal.</p>
    """
    await client.send_email(to=parent_email, subject=f"Approval needed: {brief.title} on Teenure", html=html)


async def send_campaign_blocked_notice_to_rep(rep_email: str, client: ResendClient) -> None:
    html = """
    <p>A campaign invitation was declined on your behalf by your
    parent/guardian. You can see your other available campaigns in
    your Teenure dashboard.</p>
    """
    await client.send_email(to=rep_email, subject="A campaign invitation was declined", html=html)


async def send_campaign_payment_failed_email(brand_email: str, campaign_title: str, client: ResendClient) -> None:
    """payment_intent.payment_failed webhook (Build Prompt 10 deliverable
    3: "notify brand"). Points the brand at retry-payment rather than
    activate -- the campaign is now in 'payment_failed', which
    app/routers/brands.py's activate_campaign explicitly rejects."""
    html = f"""
    <p>The payment for your campaign <strong>{campaign_title}</strong>
    couldn't be completed. No reps have been charged and nothing else
    about your campaign has changed.</p>
    <p>Retry payment from your Teenure dashboard to activate it.</p>
    """
    await client.send_email(to=brand_email, subject=f"Payment failed for {campaign_title}", html=html)


async def send_milestone_submitted_email(brand_email: str, *, campaign_title: str, milestone_title: str, client: ResendClient) -> None:
    """Build Prompt 8B deliverable 4: 'brand_confirmation' milestones
    notify the brand a submission is awaiting review (the
    'rep_submission' path skips this -- no brand action is required
    before its 24h auto-release, per the same deliverable)."""
    html = f"""
    <p>A rep has submitted evidence for the milestone
    <strong>{milestone_title}</strong> on your campaign
    <strong>{campaign_title}</strong>. Review it from your Teenure
    dashboard to confirm and release payout.</p>
    """
    await client.send_email(to=brand_email, subject=f"Milestone submitted: {campaign_title}", html=html)


async def send_milestone_disputed_email(rep_email: str, *, campaign_title: str, milestone_title: str, client: ResendClient) -> None:
    """Build Prompt 8B deliverable 7: the rep is notified when a brand
    flags their milestone submission for admin review."""
    html = f"""
    <p>The brand behind <strong>{campaign_title}</strong> has flagged
    your submission for the milestone <strong>{milestone_title}</strong>
    for review. An admin will review the evidence and follow up -- no
    action is needed from you right now.</p>
    """
    await client.send_email(to=rep_email, subject=f"Milestone under review: {campaign_title}", html=html)


async def send_exclusivity_purchase_confirmed_email(
    brand_email: str, *, category: str, city: str | None, starts_at: str, ends_at: str, client: ResendClient
) -> None:
    """Build Prompt 8C deliverable 4: payment_intent.succeeded webhook
    for a category_exclusivity_agreements row -- exact copy per the
    spec: "Your category exclusivity in [category] in [city or 'all
    markets'] from [dates] is now active." """
    where = city or "all markets"
    html = f"""
    <p>Your category exclusivity in <strong>{category}</strong> in
    <strong>{where}</strong> from {starts_at} to {ends_at} is now
    active.</p>
    """
    await client.send_email(to=brand_email, subject=f"Category exclusivity active: {category}", html=html)


async def send_exclusivity_purchase_failed_email(brand_email: str, *, category: str, client: ResendClient) -> None:
    """Build Prompt 8C deliverable 4: payment_intent.payment_failed --
    failed payment means no exclusivity, so the brand is told plainly."""
    html = f"""
    <p>The payment for your category exclusivity request in
    <strong>{category}</strong> failed. No exclusivity was granted and
    you have not been charged.</p>
    """
    await client.send_email(to=brand_email, subject=f"Category exclusivity payment failed: {category}", html=html)


async def send_exclusivity_cancelled_email(
    brand_email: str, *, category: str, refund_cents: int, client: ResendClient
) -> None:
    """Build Prompt 8C deliverable 7: admin-initiated cancellation with
    proration -- the brand is told the refund amount."""
    html = f"""
    <p>Your category exclusivity in <strong>{category}</strong> has been
    cancelled by Teenure. A refund of ${refund_cents / 100:.2f} has been
    issued to your original payment method.</p>
    """
    await client.send_email(to=brand_email, subject=f"Category exclusivity cancelled: {category}", html=html)


async def send_account_suspended_email(rep_email: str, client: ResendClient) -> None:
    html = """
    <p>Your Teenure account has been suspended by your parent/guardian.
    You won't be able to accept new campaigns until it's reinstated.</p>
    """
    await client.send_email(to=rep_email, subject="Your Teenure account has been suspended", html=html)


async def send_account_approved_email(to: str, *, account_type: str, client: ResendClient) -> None:
    html = f"""
    <p>Good news -- your Teenure {account_type} account has been approved
    by our team and is now active.</p>
    """
    await client.send_email(to=to, subject="Your Teenure account has been approved", html=html)


async def send_account_rejected_email(to: str, *, account_type: str, reason: str, client: ResendClient) -> None:
    """Build Prompt 13 deliverable 1: rejection reason must be sent to
    the applicant via email."""
    html = f"""
    <p>We've reviewed your Teenure {account_type} application and
    weren't able to approve it at this time.</p>
    <p><strong>Reason:</strong> {reason}</p>
    <p>If you believe this was a mistake, reply to this email and
    we'll take another look.</p>
    """
    await client.send_email(to=to, subject="Update on your Teenure application", html=html)


async def send_milestone_dispute_resolved_email(
    to: str, milestone_title: str, *, confirmed: bool, client: ResendClient
) -> None:
    outcome = "confirmed and payout released" if confirmed else "sent back for the brand to review again"
    html = f"""
    <p>An admin has resolved the dispute for the milestone
    <strong>{milestone_title}</strong>. It was {outcome}.</p>
    """
    await client.send_email(to=to, subject=f"Milestone dispute resolved: {milestone_title}", html=html)


async def send_digest_email(
    parent_email: str,
    client: ResendClient,
    *,
    rep_display_name: str,
    campaigns_completed_this_month: int,
    earnings_this_month_cents: int,
    lifetime_earnings_cents: int,
    profile_completeness_score: int,
    profile_completeness_change: int | None,
    active_categories: list[str],
) -> None:
    """Content is deliberately allow-listed: campaigns completed,
    earnings, profile-completeness change, active categories. Never
    recruiter message content, submission text/files, or brand contact
    details (Section 9A) -- there is no code path in this function that
    could include them, since it never receives them as input."""
    change_line = (
        f"Profile completeness changed by {profile_completeness_change:+d} points."
        if profile_completeness_change is not None
        else "This is your first digest, so there's no prior score to compare to."
    )
    categories_line = ", ".join(active_categories) if active_categories else "none this month"
    html = f"""
    <p>Here's {rep_display_name}'s Teenure activity summary.</p>
    <ul>
      <li>Campaigns completed this month: {campaigns_completed_this_month}</li>
      <li>Earnings this month: ${earnings_this_month_cents / 100:.2f}</li>
      <li>Lifetime earnings: ${lifetime_earnings_cents / 100:.2f}</li>
      <li>Profile completeness: {profile_completeness_score}/100 -- {change_line}</li>
      <li>Categories active in this month: {categories_line}</li>
    </ul>
    """
    await client.send_email(to=parent_email, subject="Your Teenure monthly digest", html=html)
