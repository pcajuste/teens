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
  role: "rep";
  date_of_birth: string;
  parent_email?: string;
}

export interface SignupResponse {
  id: string;
  email: string;
  role: string;
  account_status: string;
}

export interface ApiErrorBody {
  detail: {
    code: string;
    message: string;
  };
}
