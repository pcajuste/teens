-- ──────────────────────────────────────────────────────────────────
-- INDEXES — Section 7's Indexes block, verbatim, plus the two extra
-- indexes called out in Build Prompt 2.
-- ──────────────────────────────────────────────────────────────────

CREATE INDEX idx_rep_profiles_categories ON public.rep_profiles USING GIN (categories);
CREATE INDEX idx_rep_profiles_city ON public.rep_profiles (city);
CREATE INDEX idx_rep_profiles_graduation_year ON public.rep_profiles (graduation_year);
CREATE INDEX idx_rep_profiles_recruiter_visible ON public.rep_profiles (recruiter_visible) WHERE recruiter_visible = TRUE;
CREATE INDEX idx_campaigns_brand ON public.campaigns (brand_id);
CREATE INDEX idx_campaigns_status ON public.campaigns (status);
CREATE INDEX idx_campaigns_categories ON public.campaigns USING GIN (target_categories);
CREATE INDEX idx_campaign_reps_rep ON public.campaign_reps (rep_id);
CREATE INDEX idx_campaign_reps_status ON public.campaign_reps (status);
CREATE INDEX idx_campaign_reps_parent_approval
  ON public.campaign_reps (parent_approval_status, parent_approval_deadline)
  WHERE parent_approval_status = 'pending';
CREATE INDEX idx_parent_auth_tokens_expiry ON public.parent_auth_tokens (expires_at) WHERE used_at IS NULL;

-- Build Prompt 2 additions:
CREATE INDEX idx_parent_records_rep ON public.parent_records (rep_id);
CREATE INDEX idx_campaigns_status_category ON public.campaigns (status, target_categories);
-- Supports the parent-approval queue filtering campaigns by status +
-- category. Note: target_categories is TEXT[]; a plain btree composite
-- index on (status, target_categories) supports equality/range on
-- status plus array-equality on target_categories as specified in
-- Prompt 2's literal text. Array *containment* queries (`@>` / `&&`)
-- would need target_categories in a GIN index instead
-- (idx_campaigns_categories above already covers that access pattern) --
-- this index is additive, not a replacement.
