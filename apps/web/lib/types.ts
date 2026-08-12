export type SchoolType = "public" | "private" | "charter" | "homeschool";

export interface RepProfile {
  id: string;
  display_name: string;
  school_name: string;
  school_type: SchoolType | null;
  city: string;
  state: string;
  graduation_year: number;
  bio: string | null;
  categories: string[];
  instagram_handle: string | null;
  tiktok_handle: string | null;
  recruiter_visible: boolean;
  total_campaigns_completed: number;
  total_earnings_cents: number;
  average_rating: number | null;
  profile_completeness_score: number;
}

export type RepProfilePreview = Omit<
  RepProfile,
  "id" | "recruiter_visible" | "total_earnings_cents"
>;

export interface RepProfileUpdateRequest {
  display_name: string;
  school_name: string;
  school_type: SchoolType | null;
  city: string;
  state: string;
  graduation_year: number;
  bio: string | null;
  categories: string[];
  instagram_handle: string | null;
  tiktok_handle: string | null;
}

export interface CampaignSummary {
  id: string;
  title: string;
  product_name: string;
  campaign_goal: string;
  deliverables_description: string;
  target_categories: string[];
  target_cities: string[];
  payout_per_rep_cents: number | null;
  start_date: string;
  end_date: string;
}

export type ParentApprovalStatus = "not_required" | "pending" | "approved" | "blocked";

export interface CampaignParticipation {
  campaign_id: string;
  status: string;
  ftc_disclosure_accepted: boolean;
  parent_approval_status: ParentApprovalStatus;
  parent_approval_deadline: string | null;
  submission_text: string | null;
  submission_file_urls: string[];
  revision_note: string | null;
  payout_cents: number | null;
  payout_status: string | null;
  invited_at: string;
  accepted_at: string | null;
  submitted_at: string | null;
  confirmed_at: string | null;
  paid_at: string | null;
}

export interface Earnings {
  pending_cents: number;
  confirmed_cents: number;
  paid_cents: number;
  lifetime_paid_cents: number;
}

export interface MeResponse {
  id: string;
  email: string;
  role: string;
  account_status: string;
  pending_reason: "awaiting_parental_consent" | "pending_admin_approval" | null;
}

export interface SignupRequest {
  email: string;
  password: string;
  role: "rep" | "brand" | "recruiter";
  date_of_birth: string;
  parent_email?: string;
}

export interface SignupResponse {
  id: string;
  email: string;
  role: string;
  account_status: string;
}

// ── Brand Portal ──────────────────────────────────────────────────

export interface BrandProfile {
  id: string;
  company_name: string;
  website: string | null;
  has_ein_on_file: boolean;
  industry: string | null;
  target_categories: string[];
  verified: boolean;
}

export interface BrandProfileUpdateRequest {
  company_name: string;
  website: string | null;
  ein: string | null;
  industry: string | null;
  target_categories: string[];
}

export type CampaignStatus =
  | "draft"
  | "pending_payment"
  | "payment_failed"
  | "active"
  | "paused"
  | "completed"
  | "cancelled";

/** Structural shape shared by the rep-facing CampaignSummary and the
 * brand-facing Campaign -- components that only render the brief
 * itself (goal/deliverables/categories/payout) accept this instead of
 * either concrete type, so the same renderer (components/campaigns/campaign-brief.tsx)
 * works for both portals (Build Prompt 9 deliverable 2: reuse the
 * rep-facing renderer, don't build a second one). */
export interface CampaignBriefLike {
  title: string;
  product_name: string;
  campaign_goal: string;
  deliverables_description: string;
  prohibited_content?: string | null;
  target_categories: string[];
  payout_per_rep_cents: number | null;
}

export interface Campaign extends CampaignBriefLike {
  id: string;
  status: CampaignStatus;
  target_cities: string[];
  max_reps: number;
  reps_accepted_count: number;
  budget_cents: number;
  platform_fee_cents: number;
  rep_pool_cents: number;
  start_date: string;
  end_date: string;
  created_at: string;
  updated_at: string;
}

export interface CampaignBriefRequest {
  title: string;
  product_name: string;
  campaign_goal: string;
  key_messaging: string;
  prohibited_content: string | null;
  deliverables_description: string;
  target_categories: string[];
  target_cities: string[];
  max_reps: number;
  budget_cents: number;
  start_date: string;
  end_date: string;
}

export interface ActivateCampaignResponse {
  id: string;
  status: CampaignStatus;
  stripe_payment_intent_client_secret: string;
}

export interface CancelCampaignResponse {
  id: string;
  status: CampaignStatus;
  refund_pending: boolean;
}

export interface RepBrowseCard {
  rep_id: string;
  city: string;
  state: string;
  graduation_year: number;
  school_type: SchoolType | null;
  categories: string[];
  profile_completeness_score: number;
  average_rating: number | null;
  total_campaigns_completed: number;
}

export interface InviteResult {
  rep_id: string;
  campaign_rep_id: string | null;
  status: "invited" | "already_invited" | "campaign_full" | "rep_not_found";
}

export interface CampaignRep {
  id: string;
  rep_id: string;
  status: string;
  ftc_disclosure_accepted: boolean;
  parent_approval_status: ParentApprovalStatus;
  submission_text: string | null;
  submission_file_urls: string[];
  revision_note: string | null;
  brand_rating: number | null;
  brand_rating_note: string | null;
  payout_cents: number | null;
  payout_status: string | null;
  invited_at: string;
  accepted_at: string | null;
  submitted_at: string | null;
  confirmed_at: string | null;
  paid_at: string | null;
}

// ── Recruiter Portal ──────────────────────────────────────────────

export type InstitutionType = "college" | "employer";

export interface RecruiterProfile {
  id: string;
  institution_name: string;
  institution_type: InstitutionType;
  website: string | null;
  verified: boolean;
}

export interface RecruiterProfileUpdateRequest {
  institution_name: string;
  institution_type: InstitutionType;
  website: string | null;
}

export interface RecruiterCredits {
  contact_credits_remaining: number;
  credits_reset_date: string | null;
  low_credit_warning: boolean;
}

/** GET /recruiters/reps/search -- no PII, no credit cost. */
export interface RecruiterSearchCard {
  rep_id: string;
  city: string;
  state: string;
  graduation_year: number;
  school_type: SchoolType | null;
  categories: string[];
  profile_completeness_score: number;
  average_rating: number | null;
  total_campaigns_completed: number;
}

/** GET /recruiters/reps/:id -- full identifying profile, costs 1 credit
 * (deducted server-side before this is ever returned -- lib/api.ts's
 * response is the only source of truth for the new credit balance,
 * never a locally-decremented counter). */
export interface RecruiterRepDetail {
  rep_id: string;
  display_name: string;
  school_name: string;
  school_type: SchoolType | null;
  city: string;
  state: string;
  graduation_year: number;
  bio: string | null;
  categories: string[];
  instagram_handle: string | null;
  tiktok_handle: string | null;
  total_campaigns_completed: number;
  average_rating: number | null;
  profile_completeness_score: number;
}

export interface RecruiterContactRequest {
  message_text: string;
}

export interface RecruiterContactResponse {
  id: string;
  rep_id: string;
  message_text: string;
  messaged_at: string;
}

export interface RecruiterSaveRequest {
  list_name?: string | null;
}

export interface RecruiterSavedProfile {
  rep_id: string;
  list_name: string | null;
  saved_at: string;
}

export interface RecruiterCreditTopUpResponse {
  stripe_payment_intent_client_secret: string;
}

export interface RecruiterSearchFilters {
  graduation_year?: number;
  city?: string;
  state?: string;
  categories?: string[];
  min_campaigns?: number;
  min_rating?: number;
  limit?: number;
  offset?: number;
}

export interface RecruiterCreditTopUpRequest {
  credits: number;
}

export type SubscriptionPlan = "monthly" | "annual";

export interface SubscriptionCheckoutRequest {
  plan: SubscriptionPlan;
}

export interface SubscriptionCheckoutResponse {
  checkout_url: string;
}

/** GET /recruiters/messages -- recruiter-facing list of sent messages
 * with read-receipt status (Build Prompt 12 deliverable 4). */
export interface RecruiterMessage {
  id: string;
  rep_id: string;
  rep_display_name: string;
  message_text: string;
  read_at: string | null;
  messaged_at: string;
}

// Matches apps/api/app/core/errors.py's response shape exactly --
// lib/api.ts's parseError reads this shape directly (not this type,
// which exists for callers that want to type a raw error body).
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}

// ══════════════════════════════════════════════════════════════════
// Admin Portal (Build Prompt 13)
// ══════════════════════════════════════════════════════════════════

export interface AdminQueueEntry {
  user_id: string;
  email: string;
  role: string;
  account_status: string;
  pending_reason: "awaiting_parent_consent" | "awaiting_admin_approval";
  display_name: string;
  created_at: string;
}

export interface AdminCampaign {
  id: string;
  title: string;
  status: string;
  brand_name: string;
  budget_cents: number;
  target_categories: string[];
  flagged_at: string | null;
  flagged_reason: string | null;
  resolved_at: string | null;
  resolution_action: string | null;
  created_at: string;
}

export interface AdminStuckPayment {
  campaign_rep_id: string;
  campaign_id: string;
  rep_id: string;
  payout_cents: number | null;
  payout_status: string;
  stripe_transfer_id: string | null;
  payout_processing_started_at: string | null;
  hours_stuck: number;
}

export interface AdminRevenuePeriod {
  period: string;
  brand_campaign_fees_cents: number;
  intelligence_subscription_cents: number;
  recruiter_active_subscriptions: number;
}

export interface AdminCountBreakdown {
  by_city?: { city: string; state: string; count: number }[];
  by_category?: { category: string; count: number }[];
  by_status?: { status: string; count: number }[];
}

export interface AdminConsentStatusEntry {
  consent_state: string;
  count: number;
}

export interface AdminOutlierBrand {
  brand_id: string;
  company_name: string;
  rating_count: number;
  average_rating: number;
  reason: string;
}

export interface AdminParentSuspendedRep {
  rep_id: string;
  rep_user_id: string;
  display_name: string;
  parent_id: string;
  suspended_by_parent_at: string;
}

export interface AdminSafetyReport {
  id: string;
  reporter_rep_id: string;
  reporter_display_name: string;
  campaign_id: string | null;
  reason: string;
  description: string | null;
  status: string;
  created_at: string;
  resolved_at: string | null;
  resolution_note: string | null;
}
