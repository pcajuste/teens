export type SchoolType = "public" | "private" | "charter" | "homeschool";

export interface TalentProfile {
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
  challenges_submitted_count?: number;
  challenges_converted_count?: number;
  challenge_conversion_rate?: number | null;
  badges: Badge[];
  badges_earned_count: number;
  // Multi-track fields (ATHLETICS-4): brand_completeness_score is the
  // renamed/parallel counterpart to profile_completeness_score for the
  // athletic track's sibling; profile_completeness_score itself stays
  // the cross-track GREATEST computed server-side, so it's still safe
  // to read directly for a single "your profile is N% complete" number.
  enabled_tracks: string[];
  brand_completeness_score: number;
  athletic_completeness_score: number;
  athletic_seasons_completed: number;
  athletic_recruiter_interest_count: number;
}

export type TalentProfilePreview = Omit<
  TalentProfile,
  "id" | "recruiter_visible" | "total_earnings_cents"
>;

// ── Learning Modules and Verified Badges (Build Prompt 8H) ──────────

export interface Badge {
  module_id: string;
  badge_title: string;
  badge_description: string;
  badge_color: string;
  badge_icon: string | null;
  earned_at: string;
}

export type ContentBlockType = "text" | "video_url" | "image_url" | "quiz";

export interface QuizQuestionPublic {
  question: string;
  options: string[];
  // correct_index intentionally absent -- never sent by the server.
}

export interface ContentBlockPublic {
  type: ContentBlockType;
  content: string | QuizQuestionPublic[];
}

export type ModuleStatus = "draft" | "active" | "archived";
export type CompletionStatus = "in_progress" | "passed" | "failed";

export interface TalentProgress {
  status: CompletionStatus;
  attempts: number;
  quiz_score: number | null;
  last_attempt_at: string | null;
}

export interface ModuleAvailable {
  id: string;
  title: string;
  description: string;
  category: string | null;
  badge_title: string;
  badge_description: string;
  badge_color: string;
  badge_icon: string | null;
  estimated_minutes: number;
  passing_score: number | null;
  talent_progress: TalentProgress | null;
}

export interface ModuleCompleted {
  module_id: string;
  title: string;
  category: string | null;
  badge_title: string;
  badge_description: string;
  badge_color: string;
  badge_icon: string | null;
  passed_at: string | null;
  quiz_score: number | null;
}

export interface ModuleContent {
  id: string;
  title: string;
  description: string;
  category: string | null;
  content_blocks: ContentBlockPublic[];
  passing_score: number | null;
  badge_title: string;
  badge_description: string;
  badge_color: string;
  badge_icon: string | null;
  estimated_minutes: number;
  status: ModuleStatus;
}

export interface ModuleStartResponse {
  module: ModuleContent;
  completion: TalentProgress;
}

export interface WrongAnswerEntry {
  question_index: number;
  correct_index: number;
  talent_answer_index: number;
}

export interface ModuleCompleteResponse {
  passed: boolean;
  quiz_score: number | null;
  passing_score?: number | null;
  badge?: {
    badge_title: string;
    badge_description: string;
    badge_color: string;
    badge_icon: string | null;
  } | null;
  profile_completeness_score?: number | null;
  correct_answers?: WrongAnswerEntry[] | null;
}

export interface AdminModule {
  id: string;
  title: string;
  description: string;
  category: string | null;
  content_blocks: ContentBlockPublic[];
  passing_score: number | null;
  badge_title: string;
  badge_description: string;
  badge_color: string;
  badge_icon: string | null;
  estimated_minutes: number;
  status: ModuleStatus;
  created_at: string;
  updated_at: string;
  completion_count: number;
  pass_rate: number | null;
  average_attempts: number | null;
  in_progress_count: number;
}

// GET /talents/me/achievement-record -- wraps TalentProfilePreview rather
// than repeating its fields, matching the backend's
// AchievementRecordResponse shape (see apps/api/app/schemas/talents.py)
// so this can never drift from the profile-preview data.
export interface AchievementRecord {
  generated_at: string;
  record: TalentProfilePreview;
}

export interface TalentProfileUpdateRequest {
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

// ── Milestone payments (Build Prompt 8B) ────────────────────────────

export type VerificationMethod = "brand_confirmation" | "talent_submission";

/** One row of the `milestones` array sent in POST /brands/campaigns
 * when payment_type='milestone' -- matches
 * apps/api/app/schemas/brands.py's MilestoneRequest field-for-field.
 * Cross-milestone rules (percentages sum to 100, sequential numbering,
 * at least one sequence_required, non-sequential trailing-only) are
 * validated server-side; the milestone builder only enforces the
 * percentage-sum check and the 2-5 count client-side as a UX guard. */
export interface MilestoneRequest {
  milestone_number: number;
  title: string;
  description: string | null;
  verification_method: VerificationMethod;
  payout_percentage: number;
  sequence_required: boolean;
  /** Optional count-based milestone support: when set, the talent must
   * submit this many times before the milestone is considered
   * complete (e.g. 3 for "publish 3 pieces of content"). Leave
   * undefined for an ordinary single-submission milestone -- most
   * milestones won't set this. */
  threshold_count?: number | null;
}

/** Per-milestone entry within GET /talents/campaigns/active for a
 * milestone campaign -- matches
 * apps/api/app/schemas/talents.py's MilestoneParticipationResponse.
 * `actionable` is server-computed sequence awareness; the frontend
 * never re-derives it. */
export interface MilestoneParticipation {
  id: string;
  campaign_milestone_id: string;
  milestone_number: number;
  title: string;
  description: string | null;
  verification_method: VerificationMethod;
  payout_percentage: number;
  sequence_required: boolean;
  status: string;
  actionable: boolean;
  payout_cents: number | null;
  payout_status: string;
  /** Set only for a count-based milestone (see MilestoneRequest). When
   * present, the talent UI should render "current_count of threshold_count"
   * progress instead of a flat pending/actionable state. */
  threshold_count: number | null;
  current_count: number;
  submitted_at: string | null;
  confirmed_at: string | null;
  paid_at: string | null;
}

/** Brand's per-talent milestone progress view -- GET
 * /brands/campaigns/:id/talents/:talent_id/milestones, matches
 * apps/api/app/schemas/brands.py's MilestoneProgressResponse. */
export interface MilestoneProgress {
  id: string;
  campaign_milestone_id: string;
  milestone_number: number;
  title: string;
  verification_method: VerificationMethod;
  payout_percentage: number;
  status: string;
  talent_submission_text: string | null;
  talent_submission_file_urls: string[];
  payout_cents: number | null;
  payout_status: string;
  dispute_flag: boolean;
  threshold_count: number | null;
  current_count: number;
  submitted_at: string | null;
  confirmed_at: string | null;
  paid_at: string | null;
}

export interface SubmitMilestoneRequest {
  submission_text: string;
  submission_file_urls: string[];
}

/** One campaign's milestone-level earnings detail within GET
 * /talents/earnings -- matches
 * apps/api/app/schemas/talents.py's MilestoneEarningsEntry. */
export interface MilestoneEarningsEntry {
  campaign_id: string;
  campaign_title: string;
  payout_per_talent_cents: number | null;
  milestones_completed_count: number;
  total_milestone_payout_cents: number;
  milestones: MilestoneParticipation[];
}

export interface CampaignSummary {
  id: string;
  title: string;
  product_name: string;
  campaign_goal: string;
  deliverables_description: string;
  target_categories: string[];
  target_cities: string[];
  payout_per_talent_cents: number | null;
  start_date: string;
  end_date: string;
}

export type ParentApprovalStatus =
  | "not_required"
  | "pending"
  | "approved"
  | "blocked";

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
  payment_type: PaymentType;
  milestones: MilestoneParticipation[];
  milestones_completed_count: number;
  total_milestone_payout_cents: number;
}

export interface Earnings {
  pending_cents: number;
  confirmed_cents: number;
  paid_cents: number;
  lifetime_paid_cents: number;
  milestone_campaigns: MilestoneEarningsEntry[];
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
  role: "talent" | "brand" | "recruiter";
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

export type PaymentType = "flat" | "milestone";

/** Structural shape shared by the talent-facing CampaignSummary and the
 * brand-facing Campaign -- components that only render the brief
 * itself (goal/deliverables/categories/payout) accept this instead of
 * either concrete type, so the same renderer (components/campaigns/campaign-brief.tsx)
 * works for both portals (Build Prompt 9 deliverable 2: reuse the
 * talent-facing renderer, don't build a second one). */
export interface CampaignBriefLike {
  title: string;
  product_name: string;
  campaign_goal: string;
  deliverables_description: string;
  prohibited_content?: string | null;
  target_categories: string[];
  payout_per_talent_cents: number | null;
}

export interface Campaign extends CampaignBriefLike {
  id: string;
  status: CampaignStatus;
  target_cities: string[];
  max_talents: number;
  talents_accepted_count: number;
  budget_cents: number;
  platform_fee_cents: number;
  talent_pool_cents: number;
  start_date: string;
  end_date: string;
  payment_type: PaymentType;
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
  max_talents: number;
  budget_cents: number;
  start_date: string;
  end_date: string;
  payment_type?: PaymentType;
  milestones?: MilestoneRequest[];
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

export interface TalentBrowseCard {
  talent_id: string;
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
  talent_id: string;
  campaign_talent_id: string | null;
  status: "invited" | "already_invited" | "campaign_full" | "talent_not_found";
}

export interface CampaignTalent {
  id: string;
  talent_id: string;
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
  milestones_completed_count: number;
  total_milestone_payout_cents: number;
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

/** GET /recruiters/talents/search -- no PII, no credit cost. */
export interface RecruiterSearchCard {
  talent_id: string;
  city: string;
  state: string;
  graduation_year: number;
  school_type: SchoolType | null;
  categories: string[];
  profile_completeness_score: number;
  average_rating: number | null;
  total_campaigns_completed: number;
}

/** GET /recruiters/talents/:id -- full identifying profile, costs 1 credit
 * (deducted server-side before this is ever returned -- lib/api.ts's
 * response  is the only source of truth for the new credit balance,
 * never a locally-decremented counter). */
export interface RecruiterTalentDetail {
  talent_id: string;
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
  total_earnings_cents: number;
  average_rating: number | null;
  profile_completeness_score: number;
}

export interface RecruiterContactRequest {
  message_text: string;
}

export interface RecruiterContactResponse {
  id: string;
  talent_id: string;
  message_text: string;
  messaged_at: string;
}

export interface RecruiterSaveRequest {
  list_name?: string | null;
}

export interface RecruiterSavedProfile {
  talent_id: string;
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
  talent_id: string;
  talent_display_name: string;
  message_text: string;
  read_at: string | null;
  messaged_at: string;
}

// Matches apps/api/app/core/errors.py's response  shape exactly --
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
  campaign_talent_id: string;
  campaign_id: string;
  talent_id: string;
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

export interface AdminModuleAnalyticsPerModuleEntry {
  module_id: string;
  title: string;
  category: string | null;
  completion_count: number;
  pass_rate: number | null;
  average_attempts: number | null;
}

export interface AdminModuleAnalyticsBadgeEntry {
  badge_title: string;
  category: string | null;
  earned_count: number;
}

export interface AdminModuleAnalytics {
  total_modules: number;
  draft_modules: number;
  active_modules: number;
  archived_modules: number;
  completions_in_progress: number;
  completions_passed: number;
  completions_failed: number;
  per_module: AdminModuleAnalyticsPerModuleEntry[];
  modules_flagged_low_pass_rate: string[];
  modules_flagged_high_attempts: string[];
  badge_distribution: AdminModuleAnalyticsBadgeEntry[];
  ftc_module_readiness: {
    attempted_reps: number;
    passed_reps: number;
    pass_percentage: number | null;
  } | null;
}

export interface AdminOutlierBrand {
  brand_id: string;
  company_name: string;
  rating_count: number;
  average_rating: number;
  reason: string;
}

export interface AdminParentSuspendedTalent {
  talent_id: string;
  talent_user_id: string;
  display_name: string;
  parent_id: string;
  suspended_by_parent_at: string;
}

export interface AdminSafetyReport {
  id: string;
  reporter_talent_id: string;
  reporter_display_name: string;
  campaign_id: string | null;
  reason: string;
  description: string | null;
  status: string;
  created_at: string;
  resolved_at: string | null;
  resolution_note: string | null;
}

// ── Category Exclusivity (Build Prompt 8C) ──────────────────────────
// Matches apps/api/app/schemas/exclusivity.py field-for-field.

export interface ExclusivityCheckResponse {
  available: boolean;
  conflict: { exists: boolean };
}

export interface ExclusivityPricingResponse {
  days: number;
  rate_per_day_cents: number;
  total_cents: number;
  starts_at: string;
  ends_at: string;
}

export interface ExclusivityPurchaseRequest {
  category: string;
  city: string | null;
  starts_at: string;
  ends_at: string;
}

export interface ExclusivityPurchaseResponse {
  agreement_id: string;
  client_secret: string;
  fee_cents: number;
  starts_at: string;
  ends_at: string;
}

export type ExclusivityAgreementStatus = "active" | "expired" | "cancelled";
export type ExclusivityPaymentStatus =
  | "pending"
  | "paid"
  | "refunded"
  | "partially_refunded"
  | "failed";

export interface ExclusivityAgreement {
  id: string;
  category: string;
  city: string | null;
  starts_at: string;
  ends_at: string;
  status: ExclusivityAgreementStatus;
  payment_status: ExclusivityPaymentStatus;
  fee_cents: number;
  refund_cents: number | null;
}

export interface AdminExclusivityAgreement extends ExclusivityAgreement {
  brand_id: string;
  stripe_payment_intent_id: string;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
}

export interface AdminExclusivityActiveAgreement extends AdminExclusivityAgreement {
  days_remaining: number;
}

export interface AdminExclusivityListResponse {
  agreements: AdminExclusivityAgreement[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminExclusivityCancelRequest {
  cancellation_reason: string;
}

export interface AdminExclusivityCancelResponse {
  id: string;
  status: ExclusivityAgreementStatus;
  cancelled_at: string;
  refund_cents: number;
}

export interface ExclusivityCategoryFrequency {
  category: string;
  purchase_count: number;
}

export interface AdminExclusivityAnalyticsResponse {
  total_revenue_cents: number;
  active_count: number;
  categories_by_purchase_frequency: ExclusivityCategoryFrequency[];
  average_agreement_length_days: number;
}

// ── Skill Challenges (Build Prompt 8G) ──────────────────────────────

export type ChallengeSubmissionFormat = "text" | "file" | "both";
export type ChallengeStatus = "draft" | "active" | "closed";

export interface Challenge {
  id: string;
  brand_id: string;
  title: string;
  brief: string;
  category: string;
  target_cities: string[];
  submission_format: ChallengeSubmissionFormat;
  submission_prompt: string;
  status: ChallengeStatus;
  max_submissions: number | null;
  submissions_count: number;
  conversion_count: number;
  conversion_rate: number | null;
  opens_at: string | null;
  closes_at: string | null;
  created_at: string;
  updated_at: string;
  // Build Prompt 8I content layer
  goal_text: string | null;
  rules_text: string | null;
  judging_criteria: string | null;
  prize_reward_text: string | null;
  why_text: string | null;
  moderation_status: ModerationStatus;
  rejection_reason: string | null;
  // Stripped -- never includes correct_index (issue #51).
  quiz_questions: QuizQuestionPublic[];
}

export interface ChallengeCreateRequest {
  title: string;
  brief: string;
  category: string;
  submission_format: ChallengeSubmissionFormat;
  submission_prompt: string;
  target_cities: string[];
  max_submissions: number | null;
  closes_at: string | null;
}

export interface ChallengeSubmissionTalentCard {
  talent_id: string;
  display_name: string;
  city: string;
  categories: string[];
  profile_completeness_score: number;
  campaigns_completed: number;
  average_rating: number | null;
  challenges_converted_count: number;
  challenge_conversion_rate: number | null;
}

export interface BrandChallengeSubmission {
  id: string;
  challenge_id: string;
  talent: ChallengeSubmissionTalentCard;
  submission_text: string | null;
  submission_file_urls: string[];
  status: "submitted" | "reviewed" | "converted";
  brand_note: string | null;
  submitted_at: string;
  converted_to_campaign_id: string | null;
  payout_cents: number | null;
  payout_status: string | null;
}

export interface TalentAvailableChallenge {
  id: string;
  title: string;
  brief: string;
  category: string;
  submission_format: ChallengeSubmissionFormat;
  submission_prompt: string;
  target_cities: string[];
  closes_at: string | null;
  quiz_questions: QuizQuestionPublic[];
}

export interface TalentSubmittedChallenge {
  challenge_id: string;
  challenge_title: string;
  category: string;
  submitted_at: string;
  status: "submitted" | "converted";
  campaign_id: string | null;
  campaign_title: string | null;
  payout_per_talent_cents: number | null;
  bonus_cents: number | null;
}

export interface SubmitChallengeRequest {
  submission_text: string | null;
  submission_file_urls: string[];
  disclosure_acknowledged: boolean;
}

export const CHALLENGE_CONVERSION_BONUS_DOLLARS = "$7.50";

export interface TalentChallengeSubmissionResponse {
  id: string;
  challenge_id: string;
  status: "submitted";
  submitted_at: string;
}

// ── Living Achievement Link (Build Prompt 5/6 deliverable 12/9) ─────

export interface AchievementLink {
  url: string;
  token: string;
  verified_profile_public: boolean;
  earnings_visible_on_public_profile: boolean;
}

export interface AchievementLinkVisibilityUpdate {
  verified_profile_public: boolean;
  earnings_visible_on_public_profile: boolean;
}

export interface PublicVerifiedProfile {
  public: boolean;
  display_name: string | null;
  school_name: string | null;
  graduation_year: number | null;
  city: string | null;
  categories: string[] | null;
  badges: Badge[] | null;
  total_campaigns_completed: number | null;
  average_rating: number | null;
  total_earnings_cents: number | null;
  last_updated: string | null;
}

// ── Goal Setting and Progress Tracking (Build Prompt 5/6 deliverable 13/10) ─

export type GoalType =
  | "campaigns_completed"
  | "earnings_total"
  | "categories_active"
  | "badges_earned"
  | "profile_completeness";

export interface Goal {
  id: string;
  goal_type: GoalType;
  target_value: number;
  target_date: string | null;
  current_value: number;
  progress_percentage: number;
  status: "active" | "completed" | "abandoned";
  completed_at: string | null;
  created_at: string;
  projected_completion_date: string | null;
}

export interface CreateGoalRequest {
  goal_type: GoalType;
  target_value: number;
  target_date?: string | null;
}

export interface GoalSuggestion {
  goal_type: GoalType;
  label: string;
  suggested_target_value: number;
}

export const GOAL_TYPE_LABELS: Record<GoalType, string> = {
  campaigns_completed: "Complete campaigns",
  earnings_total: "Earn money",
  categories_active: "Work in categories",
  badges_earned: "Earn badges",
  profile_completeness: "Reach profile completeness",
};

export const MAX_ACTIVE_GOALS = 3;

// ─────────────────────────────────────────────────────────────────
// Build Prompt 8I: Brand Content Templates & Delivery Framework
// ─────────────────────────────────────────────────────────────────

export interface CompanyProfile {
  logo_url: string | null;
  brand_color_primary: string | null;
  about_text: string | null;
  why_on_teenure_text: string | null;
  complete: boolean;
}

export interface CompanyProfileUpdateRequest {
  logo_url?: string | null;
  brand_color_primary?: string | null;
  about_text: string;
  why_on_teenure_text: string;
}

export type ModerationStatus = "draft" | "pending_review" | "approved" | "rejected";

export interface EligibilityCriterion {
  label: string;
  required: boolean;
}

export interface Scholarship {
  id: string;
  title: string;
  award_amount_cents: number;
  number_of_awards: number;
  eligibility_criteria: EligibilityCriterion[];
  application_requirements: string;
  why_text: string;
  image_url: string | null;
  video_url: string | null;
  deadline: string;
  moderation_status: ModerationStatus;
  rejection_reason: string | null;
  status: "draft" | "active" | "closed";
  created_at: string;
}

export interface ScholarshipCreateRequest {
  title: string;
  award_amount_cents: number;
  number_of_awards: number;
  eligibility_criteria: EligibilityCriterion[];
  application_requirements: string;
  why_text: string;
  image_url?: string | null;
  video_url?: string | null;
  deadline: string;
}

export interface ScholarshipApplication {
  id: string;
  scholarship_id: string;
  response_text: string;
  status: "submitted" | "under_review" | "awarded" | "declined";
  submitted_at: string;
  reviewed_at: string | null;
}

export interface ScholarshipApplicationBrandView {
  id: string;
  talent_id: string;
  response_text: string;
  status: string;
  submitted_at: string;
}

// Public shape only -- correct_index intentionally absent, never sent
// by the server (see Challenge.quiz_questions).
export interface QuizQuestionPublic {
  question: string;
  options: string[];
}

export interface QuizQuestionInput extends QuizQuestionPublic {
  correct_index: number;
}

export interface ChallengeContentLayerUpdateRequest {
  goal_text?: string | null;
  rules_text?: string | null;
  judging_criteria?: string | null;
  prize_reward_text?: string | null;
  why_text: string;
  quiz_questions?: QuizQuestionInput[] | null;
}

export interface QuizWrongAnswerEntry {
  question_index: number;
  correct_index: number;
  talent_answer_index: number;
}

export interface QuizResult {
  challenge_id: string;
  score: number;
  total: number;
  passed: boolean;
  wrong_answers: QuizWrongAnswerEntry[];
}

// ──────────────────────────────────────────────────────────────────
// Internship / Apprenticeship template (issue #50)
// ──────────────────────────────────────────────────────────────────

export type CompensationType = "paid" | "stipend" | "unpaid";

export interface Internship {
  id: string;
  role_title: string;
  description: string;
  time_commitment: string;
  compensation_type: CompensationType;
  compensation_why: string;
  requirements_text: string;
  application_process_text: string;
  why_text: string;
  deadline: string;
  moderation_status: ModerationStatus;
  rejection_reason: string | null;
  status: "draft" | "active" | "closed";
  created_at: string;
}

export interface InternshipCreateRequest {
  role_title: string;
  description: string;
  time_commitment: string;
  compensation_type: CompensationType;
  compensation_why: string;
  requirements_text: string;
  application_process_text: string;
  why_text: string;
  deadline: string;
}

export interface InternshipApplication {
  id: string;
  internship_id: string;
  response_text: string;
  status: "submitted" | "under_review" | "accepted" | "declined";
  submitted_at: string;
  reviewed_at: string | null;
}

export interface InternshipApplicationBrandView {
  id: string;
  talent_id: string;
  response_text: string;
  status: string;
  submitted_at: string;
}

export interface InsightEligibility {
  legal_entity_verified: boolean;
  named_contact_verified: boolean;
  business_presence_verified: boolean;
  funding_confirmed: boolean;
  content_agreement_signed: boolean;
  is_early_stage_startup: boolean;
  incorporated_3mo_or_backed: boolean;
  has_real_product: boolean;
  eligible: boolean;
  manually_reviewed_at: string | null;
}

export type InsightFeedbackFormat = "rating_scale" | "structured_qa";

export interface QAQuestion {
  id: string;
  prompt: string;
}

export interface QAAnswer {
  question_id: string;
  answer_text: string;
}

export interface InsightCampaign {
  id: string;
  title: string;
  material_url: string;
  business_question: string;
  feedback_format: InsightFeedbackFormat;
  qa_questions: QAQuestion[];
  panel_size: number;
  panel_criteria: Record<string, unknown>;
  compensation_cents: number;
  confidentiality_terms: string;
  is_startup_validation: boolean;
  moderation_status: ModerationStatus;
  rejection_reason: string | null;
  status: "draft" | "active" | "closed";
  created_at: string;
}

export interface InsightCampaignCreateRequest {
  title: string;
  material_url: string;
  business_question: string;
  feedback_format?: InsightFeedbackFormat;
  qa_questions?: QAQuestion[];
  panel_size: number;
  panel_criteria?: Record<string, unknown>;
  compensation_cents: number;
  confidentiality_terms: string;
  is_startup_validation?: boolean;
}

export interface InsightInvitation {
  panel_member_id: string;
  campaign_id: string;
  campaign_title: string;
  business_question: string;
  feedback_format: InsightFeedbackFormat;
  qa_questions: QAQuestion[];
  confidentiality_terms: string;
  compensation_cents: number;
  invited_at: string;
  responded_at: string | null;
}

export interface RatingAnswer {
  question: string;
  score: number;
}

export interface InsightResponseSubmitRequest {
  ratings?: RatingAnswer[];
  qa_answers?: QAAnswer[];
}

export interface InsightBrandResult {
  pseudonym_handle: string;
  feedback_format: InsightFeedbackFormat;
  ratings: RatingAnswer[] | null;
  qa_answers: QAAnswer[] | null;
  submitted_at: string;
}

export interface InsightBrandResults {
  feedback_format: InsightFeedbackFormat;
  released: boolean;
  responses_submitted: number;
  responses_required: number;
  results: InsightBrandResult[];
}

// ── Athletic track (ATHLETICS-6) ─────────────────────────────────────

export type AthleticSeasonStatus =
  | "draft"
  | "pending_attestation"
  | "attested"
  | "verified";

export interface SportProfile {
  id: string;
  sport: string;
  positions: string[];
  gpa: number | null;
  hudl_url: string | null;
  maxpreps_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface SportProfileUpdateRequest {
  sport: string;
  positions: string[];
  gpa: number | null;
  hudl_url: string | null;
  maxpreps_url: string | null;
}

export interface AthleticSeason {
  id: string;
  sport: string;
  season_year: number;
  season_type: string;
  team_name: string;
  level: string;
  sport_stats: Record<string, unknown>;
  coach_name: string | null;
  coach_email: string | null;
  coach_attestation_status: string;
  coach_attested_at: string | null;
  admin_verified: boolean;
  admin_verified_at: string | null;
  status: AthleticSeasonStatus;
  created_at: string;
  updated_at: string;
}

export interface CreateAthleticSeasonRequest {
  sport: string;
  season_year: number;
  season_type: string;
  team_name: string;
  level: string;
  sport_stats: Record<string, unknown>;
  coach_name: string | null;
  coach_email: string | null;
}

export interface EnableAthleticTrackResponse {
  enabled_tracks: string[];
}

export interface RequestCoachAttestationResponse {
  success: boolean;
  rate_limited: boolean;
  hours_until_resend_allowed: number | null;
  message: string;
}

export interface NilEligibility {
  state: string;
  nil_eligible_in_state: boolean;
  school_association_rules_acknowledged: boolean;
  acknowledged_at: string | null;
  notes?: string | null;
}

export interface AthleticProfileSummary {
  enabled_tracks: string[];
  athletic_seasons_completed: number;
  athletic_completeness_score: number;
  athletic_recruiter_interest_count: number;
  sport_profiles: SportProfile[];
  recent_seasons: AthleticSeason[];
  nil_eligibility: NilEligibility | null;
}

export interface PublicNilStateRule {
  state: string;
  nil_eligible: boolean;
  notes: string | null;
  effective_date: string;
}

// ── Athletic recruiter search / detail (ATHLETICS-7) ────────────────

/** GET /recruiters/talents/search?track=athletics -- no PII, no credit
 * cost, same rule as RecruiterSearchCard. */
export interface AthleticRecruiterSearchCard {
  talent_id: string;
  city: string;
  state: string;
  graduation_year: number;
  school_type: SchoolType | null;
  categories: string[];
  athletic_completeness_score: number;
  athletic_seasons_completed: number;
  athletic_recruiter_interest_count: number;
  sports: string[];
  top_sport_positions: string[];
  top_sport_gpa: number | null;
  has_film_url: boolean;
}

export interface AthleticSeasonSummary {
  sport: string;
  season_year: number;
  season_type: string;
  team_name: string;
  level: string;
  sport_stats: Record<string, unknown>;
  coach_name: string | null;
  status: AthleticSeasonStatus;
}

/** GET /recruiters/talents/:id?track=athletics -- full identifying
 * profile, costs 1 credit. No brand-track fields (earnings, campaigns,
 * ratings) -- irrelevant to an athletic recruiter. */
export interface AthleticTalentDetail {
  talent_id: string;
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
  athletic_completeness_score: number;
  athletic_seasons_completed: number;
  athletic_recruiter_interest_count: number;
  sport_profiles: SportProfile[];
  recent_seasons: AthleticSeasonSummary[];
  nil_acknowledged: boolean;
}

export interface SportsOfInterestResponse {
  sports_of_interest: string[];
  note?: string | null;
}

export interface SportsOfInterestUpdateRequest {
  sports_of_interest: string[];
}

// ── Coach attestation landing (ATHLETICS-7) ──────────────────────────

export interface CoachAttestationToken {
  valid: boolean;
  reason?: string | null;
  talent_display_name?: string | null;
  sport?: string | null;
  season_year?: number | null;
  team_name?: string | null;
  level?: string | null;
  sport_stats?: Record<string, unknown> | null;
  coach_name?: string | null;
}

export interface CoachAttestationDecision {
  success: boolean;
  reason?: string | null;
  sport?: string | null;
  season_year?: number | null;
  team_name?: string | null;
}
