-- ──────────────────────────────────────────────────────────────────
-- ROW LEVEL SECURITY
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rep_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brand_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_reps ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recruiter_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recruiter_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recruiter_saved_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.parent_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.parent_auth_tokens ENABLE ROW LEVEL SECURITY;

-- Base: users can read their own row (needed by several policies below
-- that join back to public.users to check role).
CREATE POLICY "User reads own row"
  ON public.users FOR SELECT
  USING (id = auth.uid());

-- ──────────────────────────────────────────────────────────────────
-- Cross-table RLS helper functions.
--
-- Several policies below need to look up a row in a DIFFERENT
-- RLS-protected table (e.g. "does this rep have a campaign_reps row
-- for this campaign" from within a campaigns policy, or vice versa).
-- Doing that with a plain EXISTS(...) subquery re-triggers RLS
-- evaluation on the referenced table, and several of these references
-- are mutually circular (rep_profiles -> campaign_reps -> rep_profiles,
-- campaigns -> campaign_reps -> campaigns), which Postgres detects and
-- refuses to execute ("infinite recursion detected in policy for
-- relation ...").
--
-- The standard Postgres/Supabase fix: put the cross-table lookup in a
-- SECURITY DEFINER function owned by a role that bypasses RLS (here,
-- the migration-running role, which is a superuser locally; on a real
-- Supabase project this would be a dedicated non-superuser role with
-- BYPASSRLS granted, never the anon/authenticated roles themselves).
-- The function's internal query then runs without RLS re-entering the
-- calling policy, breaking the cycle, while the function itself still
-- only returns a boolean/id -- it doesn't hand back arbitrary rows, so
-- it doesn't itself become a data-leak path.
CREATE SCHEMA IF NOT EXISTS rls;

CREATE OR REPLACE FUNCTION rls.rep_id_for_user(p_user_id UUID) RETURNS UUID
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$
  SELECT id FROM public.rep_profiles WHERE user_id = p_user_id;
$$;

CREATE OR REPLACE FUNCTION rls.is_recruiter(p_user_id UUID) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$
  SELECT EXISTS (SELECT 1 FROM public.users WHERE id = p_user_id AND role = 'recruiter');
$$;

CREATE OR REPLACE FUNCTION rls.brand_owns_campaign(p_campaign_id UUID, p_user_id UUID) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.campaigns c
    JOIN public.brand_profiles bp ON bp.id = c.brand_id
    WHERE c.id = p_campaign_id AND bp.user_id = p_user_id
  );
$$;

CREATE OR REPLACE FUNCTION rls.brand_has_rep_in_campaign(p_rep_id UUID, p_user_id UUID) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.campaign_reps cr
    JOIN public.campaigns c ON c.id = cr.campaign_id
    JOIN public.brand_profiles bp ON bp.id = c.brand_id
    WHERE cr.rep_id = p_rep_id AND bp.user_id = p_user_id
  );
$$;

-- Returns TRUE if the given rep (by rep_profiles.id) is allowed to see
-- the given campaign: they have a campaign_reps row for it AND that
-- row's parent_approval_status is not 'pending'/'blocked'.
CREATE OR REPLACE FUNCTION rls.rep_can_see_campaign(p_campaign_id UUID, p_rep_id UUID) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.campaign_reps cr
    WHERE cr.campaign_id = p_campaign_id
      AND cr.rep_id = p_rep_id
      AND cr.parent_approval_status IN ('not_required', 'approved')
  );
$$;

-- The `authenticated` role (Supabase's standard role for logged-in API
-- callers) needs USAGE + EXECUTE to call these from within its own
-- policies; it does NOT get direct SELECT on the underlying tables the
-- functions read from, so it still can't bypass RLS by querying them
-- another way. On a real Supabase project `authenticated` already
-- exists (created by the platform, not this migration). On a bare
-- local Postgres it doesn't exist until
-- scripts/local-dev/test_rls.sql creates it, so this grant is guarded
-- to keep this migration applying cleanly on a truly fresh database
-- either way.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    GRANT USAGE ON SCHEMA rls TO authenticated;
    GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA rls TO authenticated;
  END IF;
END$$;

-- ──────────────────────────────────────────────────────────────────
-- rep_profiles
-- ──────────────────────────────────────────────────────────────────

-- Reps see/edit only their own profile.
CREATE POLICY "Rep owns their profile"
  ON public.rep_profiles FOR ALL
  USING (user_id = auth.uid());

-- Recruiters see only opted-in rep profiles.
CREATE POLICY "Recruiters see opted-in reps"
  ON public.rep_profiles FOR SELECT
  USING (
    recruiter_visible = TRUE
    AND rls.is_recruiter(auth.uid())
  );

-- Brands see reps only in campaign context (via campaign_reps) --
-- i.e. a rep they have an active campaign_reps row with, regardless of
-- that rep's recruiter_visible flag (a brand campaign relationship is
-- not the same consent as recruiter discovery).
CREATE POLICY "Brands see reps via campaign context"
  ON public.rep_profiles FOR SELECT
  USING (rls.brand_has_rep_in_campaign(rep_profiles.id, auth.uid()));

-- Admin sees everything -- enforced via service role key in admin
-- portal (service_role bypasses RLS entirely; no policy needed here).

-- ──────────────────────────────────────────────────────────────────
-- brand_profiles
-- ──────────────────────────────────────────────────────────────────

CREATE POLICY "Brand owns their profile"
  ON public.brand_profiles FOR ALL
  USING (user_id = auth.uid());

-- ──────────────────────────────────────────────────────────────────
-- campaigns
-- ──────────────────────────────────────────────────────────────────

CREATE POLICY "Brand manages own campaigns"
  ON public.campaigns FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.brand_profiles bp
      WHERE bp.id = campaigns.brand_id AND bp.user_id = auth.uid()
    )
  );

-- Reps can read a campaign only if they have a campaign_reps row for
-- it AND (their parent doesn't require approval on that row, OR
-- approval has already been granted). This is Build Prompt 2's
-- required addition: block rep access at the RLS layer -- not just in
-- application code -- to a campaign where
-- campaign_reps.parent_approval_status = 'pending' (approval required,
-- not yet given). 'blocked' is likewise excluded (parent said no);
-- 'not_required' and 'approved' both pass. See rls.rep_can_see_campaign()
-- above for why this is a function call rather than an inline EXISTS.
CREATE POLICY "Rep reads own campaigns not pending parent approval"
  ON public.campaigns FOR SELECT
  USING (rls.rep_can_see_campaign(campaigns.id, rls.rep_id_for_user(auth.uid())));

-- ──────────────────────────────────────────────────────────────────
-- campaign_reps
-- ──────────────────────────────────────────────────────────────────

-- Uses rls.rep_id_for_user() (SECURITY DEFINER, bypasses RLS
-- internally) rather than an inline EXISTS(... rep_profiles ...) so
-- this policy can't re-enter rep_profiles' own RLS evaluation --
-- consistent with how the rep_profiles/campaigns policies above break
-- their own cross-table cycles.
CREATE POLICY "Rep reads/updates own campaign_reps rows"
  ON public.campaign_reps FOR ALL
  USING (campaign_reps.rep_id = rls.rep_id_for_user(auth.uid()));

CREATE POLICY "Brand reads/updates campaign_reps on own campaigns"
  ON public.campaign_reps FOR ALL
  USING (rls.brand_owns_campaign(campaign_reps.campaign_id, auth.uid()));

-- ──────────────────────────────────────────────────────────────────
-- recruiter_profiles / recruiter_contacts / recruiter_saved_profiles
-- ──────────────────────────────────────────────────────────────────

CREATE POLICY "Recruiter owns their profile"
  ON public.recruiter_profiles FOR ALL
  USING (user_id = auth.uid());

CREATE POLICY "Recruiter manages own contacts"
  ON public.recruiter_contacts FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.recruiter_profiles rp
      WHERE rp.id = recruiter_contacts.recruiter_id AND rp.user_id = auth.uid()
    )
  );

CREATE POLICY "Recruiter manages own saved profiles"
  ON public.recruiter_saved_profiles FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.recruiter_profiles rp
      WHERE rp.id = recruiter_saved_profiles.recruiter_id AND rp.user_id = auth.uid()
    )
  );

-- ──────────────────────────────────────────────────────────────────
-- parent_records / parent_auth_tokens
--
-- Parents have no Supabase auth.uid() of their own (Section 9A) -- they
-- authenticate via a magic-link flow that issues a stateless, signed
-- HS256 session token (PARENT_SESSION_SECRET) carrying
-- {parent_record_id, rep_id, exp}, verified entirely in the FastAPI
-- layer (Prompt 4A), never by Supabase's PostgREST JWT path. That
-- means the *service-role* Postgres connection (which bypasses RLS) is
-- what the API uses on a parent's behalf -- but we still want RLS to
-- fail closed for any other connection, and to give a concrete,
-- testable policy for the "matched via a parent session token, not
-- auth.uid()" requirement.
--
-- We simulate the parent session at the Postgres layer the same way
-- Supabase simulates auth.uid(): the API, after verifying the parent's
-- HS256 session token, does
--   SET LOCAL request.jwt.claims =
--     '{"parent_record_id": "<uuid>", "role": "parent"}';
-- before running the parent's query on a scoped (non-service-role)
-- connection, if/when such a scoped role is introduced. Today the
-- FastAPI service uses the service-role key for parent routes (same as
-- admin), so this policy is defense-in-depth, not the live enforcement
-- path -- documented explicitly so it isn't mistaken for the only
-- guard. See scripts/local-dev/test_rls.sql for a runnable proof using
-- this exact GUC-based simulation.
-- ──────────────────────────────────────────────────────────────────

-- Lives in `public`, not `auth`: on a real Supabase project the `auth`
-- schema is owned by supabase_auth_admin and application migrations
-- cannot create objects in it. This isn't a Supabase-provided helper
-- (auth.uid()/auth.role() are) -- it's ours, so it belongs in a schema
-- we own.
CREATE OR REPLACE FUNCTION public.parent_record_id() RETURNS UUID
LANGUAGE sql STABLE
AS $$
  SELECT (NULLIF(current_setting('request.jwt.claims', true), '')::json->>'parent_record_id')::uuid;
$$;

CREATE POLICY "Parent reads/updates only their own parent_records row"
  ON public.parent_records FOR ALL
  USING (parent_id = public.parent_record_id());
-- The rep cannot read or write parent_records directly: there is no
-- policy here matching rep_profiles.user_id = auth.uid(), so a rep's
-- normal (Supabase-JWT) connection has no clause it can satisfy and
-- default-deny applies. Reps' onboarding wizard writes parent_email by
-- calling a server-side API endpoint that creates the record using the
-- service-role key, never a rep-scoped client credential.

-- parent_auth_tokens: no user-facing policy at all (rows are only ever
-- read/written by the service-role key during the magic-link
-- request/verify flow) -- RLS is enabled with no policies, so
-- default-deny applies to any non-service-role connection, matching
-- Section 7's stated approach for this table.
