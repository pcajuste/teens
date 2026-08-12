-- Prompt 2: Database Schema & Row-Level Security
-- Section 7 of Teenure_MVP_Gameplan.md, applied verbatim, migration 3 of 4.

CREATE INDEX idx_rep_profiles_categories ON public.rep_profiles USING GIN (categories);
CREATE INDEX idx_rep_profiles_city ON public.rep_profiles (city);
CREATE INDEX idx_rep_profiles_graduation_year ON public.rep_profiles (graduation_year);
CREATE INDEX idx_rep_profiles_recruiter_visible ON public.rep_profiles (recruiter_visible) WHERE recruiter_visible = TRUE;
CREATE INDEX idx_campaigns_brand ON public.campaigns (brand_id);
CREATE INDEX idx_campaigns_status ON public.campaigns (status);
CREATE INDEX idx_campaigns_categories ON public.campaigns USING GIN (target_categories);
CREATE INDEX idx_campaign_reps_rep ON public.campaign_reps (rep_id);
CREATE INDEX idx_campaign_reps_status ON public.campaign_reps (status);
