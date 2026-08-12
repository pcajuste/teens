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

export interface ParentDashboard {
  display_name: string;
  school_name: string;
  graduation_year: number;
  categories: string[];
  profile_completeness_score: number;
  total_earnings_cents: number;
  total_campaigns_completed: number;
  challenge_activity: ParentChallengeActivity;
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
  payout_per_rep_cents: number | null;
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
