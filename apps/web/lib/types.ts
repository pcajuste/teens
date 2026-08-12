// Mirrors apps/api/app/schemas/rep.py and apps/api/app/schemas/auth.py.
// Field names/types copied directly from those files — do not guess.

export interface MeResponse {
  id: string;
  email: string;
  role: string;
  account_status: string;
  pending_reason: string | null;
}

export interface RepProfile {
  id: string;
  user_id: string;
  display_name: string;
  school_name: string;
  school_type: string | null;
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

export interface RepProfileUpdate {
  display_name?: string | null;
  school_name?: string | null;
  school_type?: string | null;
  city?: string | null;
  state?: string | null;
  graduation_year?: number | null;
  bio?: string | null;
  categories?: string[] | null;
  instagram_handle?: string | null;
  tiktok_handle?: string | null;
  recruiter_visible?: boolean | null;
}

export interface ProfilePreview {
  display_name: string;
  school_name: string;
  city: string;
  state: string;
  graduation_year: number;
  bio: string | null;
  categories: string[];
  instagram_handle: string | null;
  tiktok_handle: string | null;
  total_campaigns_completed: number;
  average_rating: number | null;
}

export interface CampaignSummary {
  campaign_reps_id: string;
  campaign_id: string;
  title: string;
  status: string;
  product_name: string;
  deliverables_description: string;
  payout_cents: number | null;
  invite_expires_at: string | null;
  start_date: string;
  end_date: string;
}

export interface EarningsBreakdown {
  pending_cents: number;
  confirmed_cents: number;
  paid_cents: number;
  lifetime_total_cents: number;
}

export interface SubmitRequest {
  submission_text: string;
  submission_file_urls: string[];
}

export interface AcceptRequest {
  ftc_disclosure_accepted: boolean;
}
