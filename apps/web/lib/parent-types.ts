export interface ParentChallengeActivitySubmission {
  challenge_title: string;
  submitted_at: string;
  status: "submitted" | "converted";
  bonus_earned_cents: number | null;
}

export interface ParentChallengeActivity {
  total_submitted: number;
  total_converted: number;
  total_bonus_earned_cents: number;
  recent_submissions: ParentChallengeActivitySubmission[];
}

export interface ParentModuleActivityBadge {
  badge_title: string;
  earned_at: string;
}

// Deliberately no quiz_score or wrong-answer fields anywhere in this
// type -- the backend never sends them to /parent/dashboard (Build
// Prompt 8H: "the outcome, not the struggle").
export interface ParentModuleActivity {
  total_started: number;
  total_passed: number;
  total_failed: number;
  badges_earned: ParentModuleActivityBadge[];
  ftc_module_passed: boolean;
}

export interface ParentScholarshipActivityApplication {
  scholarship_title: string;
  submitted_at: string;
  status: "submitted" | "under_review" | "awarded" | "declined";
  award_amount_cents: number | null;
}

export interface ParentScholarshipActivity {
  total_applied: number;
  total_awarded: number;
  total_awarded_cents: number;
  recent_applications: ParentScholarshipActivityApplication[];
}

export interface ParentInsightFeedbackActivityInvitation {
  campaign_title: string;
  confidentiality_terms: string;
  invited_at: string;
  status: "invited" | "responded";
  compensation_cents: number | null;
}

export interface ParentInsightFeedbackActivity {
  total_invited: number;
  total_responded: number;
  total_earned_cents: number;
  recent_invitations: ParentInsightFeedbackActivityInvitation[];
}

export interface ParentDashboard {
  display_name: string;
  school_name: string;
  graduation_year: number;
  categories: string[];
  profile_completeness_score: number;
  total_earnings_cents: number;
  total_campaigns_completed: number;
  challenge_activity: ParentChallengeActivity;
  module_activity: ParentModuleActivity;
  scholarship_activity: ParentScholarshipActivity;
  insight_feedback_activity: ParentInsightFeedbackActivity;
}

export interface ParentPendingCampaign {
  campaign_id: string;
  brand_name: string;
  title: string;
  product_name: string;
  campaign_goal: string;
  key_messaging: string;
  prohibited_content: string | null;
  deliverables_description: string;
  payout_per_talent_cents: number | null;
  start_date: string;
  end_date: string;
  requires_in_person_activation: boolean;
  parent_approval_deadline: string | null;
}

export type ParentCampaignDecisionStatus = "approved" | "blocked";

export interface ParentCampaignDecision {
  campaign_id: string;
  parent_approval_status: ParentCampaignDecisionStatus;
}

export interface ParentSettings {
  values_filters: string[];
  campaign_approval_required: boolean;
  digest_enabled: boolean;
}

export interface ParentDigestPreview {
  campaigns_completed_this_month: number;
  earnings_this_month_cents: number;
  lifetime_earnings_cents: number;
  profile_completeness_score: number;
  profile_completeness_change: number | null;
  active_categories: string[];
}

export interface ParentAccountControlResponse {
  account_status: string;
}

export interface ParentVerifyResponse {
  session_token: string;
  expires_at: string;
}
