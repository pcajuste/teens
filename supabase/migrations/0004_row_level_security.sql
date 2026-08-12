-- Prompt 2: Database Schema & Row-Level Security
-- Section 7 of Teenure_MVP_Gameplan.md, migration 4 of 4.
--
-- Enables RLS on every table (CLAUDE.md: "Row-level security enabled on
-- all Supabase tables from the first migration" -- Section 7's own
-- ALTER TABLE block only lists 6 tables; this migration extends that to
-- public.users and public.recruiter_saved_profiles too, since both hold
-- data an authenticated client could otherwise read/write directly and
-- neither is covered by the spec's literal list. Flagged here as an
-- addition beyond Section 7's literal SQL, required to satisfy the
-- project-wide RLS constraint.)

-- Table-level grants to the `authenticated` role (Supabase's standard
-- role for any signed-in client). RLS policies below are the actual
-- access boundary; these grants just let the role attempt DML at all,
-- matching Supabase's own convention of granting broadly and relying
-- on RLS rather than table-level GRANTs to restrict access.
GRANT SELECT, INSERT, UPDATE, DELETE ON
  public.users,
  public.rep_profiles,
  public.brand_profiles,
  public.campaigns,
  public.campaign_reps,
  public.recruiter_profiles,
  public.recruiter_contacts,
  public.recruiter_saved_profiles
TO authenticated;

ALTER TABLE public.users                     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rep_profiles               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brand_profiles             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaigns                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_reps              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recruiter_profiles         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recruiter_contacts         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recruiter_saved_profiles   ENABLE ROW LEVEL SECURITY;

-- ──────────────────────────────────────────────────────────────────
-- USERS
-- Addition beyond Section 7's literal text: a user can read/update
-- their own row. Needed because /auth/me and profile screens read
-- account_status/role, and without a policy RLS-on-with-no-policy
-- means even the owning user is locked out. Admin/service role
-- bypasses RLS entirely (Supabase service_role key), so no admin
-- policy is required here.
-- ──────────────────────────────────────────────────────────────────

CREATE POLICY "User owns their own row"
  ON public.users FOR ALL
  USING (id = auth.uid())
  WITH CHECK (id = auth.uid());

-- ──────────────────────────────────────────────────────────────────
-- REP PROFILES (verbatim from Section 7)
-- ──────────────────────────────────────────────────────────────────

-- Reps see only their own profile in edit mode
CREATE POLICY "Rep owns their profile"
  ON public.rep_profiles FOR ALL
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Recruiters see only opted-in rep profiles
CREATE POLICY "Recruiters see opted-in reps"
  ON public.rep_profiles FOR SELECT
  USING (
    recruiter_visible = TRUE
    AND EXISTS (
      SELECT 1 FROM public.users
      WHERE id = auth.uid() AND role = 'recruiter'
    )
  );

-- Brands access reps only via campaign_reps (no direct rep_profiles
-- policy for the brand role) and admin uses the service role key,
-- which bypasses RLS -- both per Section 7's closing comment.

-- ──────────────────────────────────────────────────────────────────
-- BRAND PROFILES
-- Addition: the spec's comment block doesn't give this table's SQL,
-- but Section 1A/9 require brands to only ever touch their own
-- account. A brand can read/update only their own row.
-- ──────────────────────────────────────────────────────────────────

CREATE POLICY "Brand owns their profile"
  ON public.brand_profiles FOR ALL
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- ──────────────────────────────────────────────────────────────────
-- CAMPAIGNS
-- Addition: a brand can read/write only campaigns belonging to them.
-- Reps and recruiters get no policy here at all -- deliberate no
-- direct access, per Section 7's comment ("reps and recruiters get no
-- direct table access; they interact via campaign_reps and the API
-- layer" -- the API layer uses the service-role key, so it is
-- unaffected by this table having no rep/recruiter policy).
-- ──────────────────────────────────────────────────────────────────

CREATE POLICY "Brand owns their campaigns"
  ON public.campaigns FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.brand_profiles bp
      WHERE bp.id = campaigns.brand_id AND bp.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.brand_profiles bp
      WHERE bp.id = campaigns.brand_id AND bp.user_id = auth.uid()
    )
  );

-- ──────────────────────────────────────────────────────────────────
-- CAMPAIGN REPS
-- Addition: a rep can read/update only rows where rep_id belongs to
-- them; a brand can read/update only rows where campaign_id belongs
-- to one of their campaigns. Both are needed so a rep's own client
-- can accept/decline/submit and a brand's own client can review/
-- confirm/rate, while never touching another party's rows.
-- ──────────────────────────────────────────────────────────────────

CREATE POLICY "Rep owns their campaign_reps rows"
  ON public.campaign_reps FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.rep_profiles rp
      WHERE rp.id = campaign_reps.rep_id AND rp.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.rep_profiles rp
      WHERE rp.id = campaign_reps.rep_id AND rp.user_id = auth.uid()
    )
  );

CREATE POLICY "Brand owns campaign_reps rows on their campaigns"
  ON public.campaign_reps FOR ALL
  USING (
    EXISTS (
      SELECT 1
      FROM public.campaigns c
      JOIN public.brand_profiles bp ON bp.id = c.brand_id
      WHERE c.id = campaign_reps.campaign_id AND bp.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.campaigns c
      JOIN public.brand_profiles bp ON bp.id = c.brand_id
      WHERE c.id = campaign_reps.campaign_id AND bp.user_id = auth.uid()
    )
  );

-- ──────────────────────────────────────────────────────────────────
-- RECRUITER PROFILES
-- Addition: a recruiter can read/update only their own row.
-- ──────────────────────────────────────────────────────────────────

CREATE POLICY "Recruiter owns their profile"
  ON public.recruiter_profiles FOR ALL
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- ──────────────────────────────────────────────────────────────────
-- RECRUITER CONTACTS
-- Addition: a recruiter can read/write only rows where recruiter_id
-- belongs to them. Reps deliberately get no policy here -- per
-- Section 1A they receive contacts via the GET /reps/inbox API
-- endpoint (service-role key, enforced server-side), not raw table
-- access, so a rep's own Supabase client cannot read this table at
-- all even though the message is "theirs."
-- ──────────────────────────────────────────────────────────────────

CREATE POLICY "Recruiter owns their contacts"
  ON public.recruiter_contacts FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.recruiter_profiles rp
      WHERE rp.id = recruiter_contacts.recruiter_id AND rp.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.recruiter_profiles rp
      WHERE rp.id = recruiter_contacts.recruiter_id AND rp.user_id = auth.uid()
    )
  );

-- ──────────────────────────────────────────────────────────────────
-- RECRUITER SAVED PROFILES
-- Addition: same ownership shape as recruiter_contacts.
-- ──────────────────────────────────────────────────────────────────

CREATE POLICY "Recruiter owns their saved profiles"
  ON public.recruiter_saved_profiles FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.recruiter_profiles rp
      WHERE rp.id = recruiter_saved_profiles.recruiter_id AND rp.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.recruiter_profiles rp
      WHERE rp.id = recruiter_saved_profiles.recruiter_id AND rp.user_id = auth.uid()
    )
  );
