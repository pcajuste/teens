// ---------------------------------------------------------------------------
// DEMO / FICTIONAL DATA ONLY.
//
// Everything exported from this module is hand-authored sample content for
// the logged-out marketing demo at /demo/talent. None of it is real: the talent,
// her school, the brands, the campaigns, and every dollar figure below are
// invented for illustration. Nothing here is fetched from Supabase or the
// FastAPI backend, and nothing in the demo route group ever calls
// lib/api.ts or lib/auth-context.tsx. Do not wire this module to any live
// data source.
//
// Profile completeness: the seed profile below is constructed to satisfy
// every weighted field in apps/api/app/core/profile_score.py's scoring
// rule (bio 20 + categories 20 + school_type 15 + one handle 15 + both
// handles bonus 5 + a completed campaign 25 = 100), so the "complete
// senior profile" claim in Build Prompt 6A is literally true, not just
// asserted in copy.
// ---------------------------------------------------------------------------

import type {
  CampaignParticipation,
  CampaignSummary,
  Earnings,
  TalentProfile,
} from "@/lib/types";

export const DEMO_TALENT_PROFILE: TalentProfile = {
  id: "demo-talent-maya-chen",
  display_name: "Maya Chen",
  school_name: "Crestwood High School",
  school_type: "public",
  city: "Ashwood",
  state: "OR",
  graduation_year: 2026,
  bio: "Senior at Crestwood High, captain of the varsity track team, and I make gear reviews and training-day clips for my events. I like working with brands that actually get sent to student athletes, not just influencers.",
  categories: ["athletics", "fashion", "food"],
  instagram_handle: "maya.runs.crestwood",
  tiktok_handle: "mayarunscw",
  recruiter_visible: true,
  total_campaigns_completed: 3,
  total_earnings_cents: 42500,
  average_rating: 4.8,
  profile_completeness_score: 100,
  badges: [
    {
      module_id: "demo-module-ftc",
      badge_title: "FTC Verified",
      badge_description:
        "Demonstrated understanding of sponsored content disclosure rules.",
      badge_color: "#6C3FC5",
      badge_icon: null,
      earned_at: "2026-07-02T00:00:00Z",
    },
  ],
  badges_earned_count: 1,
  enabled_tracks: [],
  brand_completeness_score: 100,
  athletic_completeness_score: 0,
  athletic_seasons_completed: 0,
  athletic_recruiter_interest_count: 0,
};

export const DEMO_AVAILABLE_CAMPAIGN_ID = "demo-campaign-summit-trail";

export const DEMO_AVAILABLE_CAMPAIGN: CampaignSummary = {
  id: DEMO_AVAILABLE_CAMPAIGN_ID,
  title: "Summit Trail Spring Restock",
  product_name: "Summit Trail Co. Trailrunner 3 sneaker",
  campaign_goal:
    "Show the new Trailrunner 3 in a real training or meet-day setting so prospective student athletes can see it in action before the spring restock.",
  deliverables_description:
    "One Instagram Reel or TikTok (30-60s) featuring the shoe during a run or practice, plus one static Instagram post with a caption mentioning the shoe by name.",
  target_categories: ["athletics", "fashion"],
  target_cities: ["Ashwood", "Portland"],
  payout_per_talent_cents: 15000,
  start_date: "2026-08-18",
  end_date: "2026-09-15",
};

export const DEMO_CONFIRMED_CAMPAIGN_ID = "demo-campaign-brightleaf-granola";

export const DEMO_CONFIRMED_CAMPAIGN: CampaignSummary = {
  id: DEMO_CONFIRMED_CAMPAIGN_ID,
  title: "Brightleaf Granola Locker Room Launch",
  product_name: "Brightleaf Foods Peak Oats granola bar",
  campaign_goal:
    "Introduce the Peak Oats bar to student athletes as a pre-practice snack via an authentic locker-room or pre-meet clip.",
  deliverables_description:
    "One TikTok (15-45s) showing the bar as part of a pre-practice routine, tagging @brightleaffoods and disclosing the partnership.",
  target_categories: ["athletics", "food"],
  target_cities: ["Ashwood"],
  payout_per_talent_cents: 12500,
  start_date: "2026-06-01",
  end_date: "2026-06-20",
};

// Mock submission evidence -- these are display-only filenames, never real
// uploaded files or real storage URLs. The state machine field shapes
// mirror CampaignParticipation from lib/types.ts / campaign_reps_repository.py
// exactly, so this reads as a real "confirmed" record would.
export const DEMO_CONFIRMED_PARTICIPATION: CampaignParticipation = {
  campaign_id: DEMO_CONFIRMED_CAMPAIGN_ID,
  status: "confirmed",
  ftc_disclosure_accepted: true,
  parent_approval_status: "approved",
  parent_approval_deadline: null,
  submission_text:
    "Pre-practice routine with the Peak Oats bar before Tuesday's track workout. #ad #BrightleafPartner",
  submission_file_urls: [
    "demo-evidence/maya-chen-brightleaf-clip.mp4",
    "demo-evidence/maya-chen-brightleaf-post.jpg",
  ],
  revision_note: null,
  payout_cents: 12500,
  payout_status: "confirmed",
  invited_at: "2026-05-20T15:00:00.000Z",
  accepted_at: "2026-05-21T12:30:00.000Z",
  submitted_at: "2026-06-05T18:45:00.000Z",
  confirmed_at: "2026-06-09T10:15:00.000Z",
  paid_at: null,
  payment_type: "flat",
  milestones: [],
  milestones_completed_count: 0,
  total_milestone_payout_cents: 0,
};

export const DEMO_EARNINGS: Earnings = {
  pending_cents: 0,
  confirmed_cents: 12500,
  paid_cents: 30000,
  lifetime_paid_cents: 42500,
  milestone_campaigns: [],
};
