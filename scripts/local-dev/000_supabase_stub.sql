-- ════════════════════════════════════════════════════════════════════
-- LOCAL-DEV-ONLY. Never run against a real Supabase project -- Supabase
-- already provides the `auth` schema, `auth.users`, and `auth.uid()`.
-- This file exists purely so the migrations in supabase/migrations/ and
-- the RLS policies they create can be applied and exercised against a
-- plain local Postgres container (no Supabase stack running), by
-- reproducing just enough of Supabase's auth surface to make
-- `auth.uid() = ...` checks work under a session-scoped GUC.
-- ════════════════════════════════════════════════════════════════════

CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid()
);

-- Mirrors Supabase's auth.uid(): reads the current request's JWT
-- "sub" claim out of a session GUC. Real Supabase sets this GUC per
-- request from the verified JWT; here a test session sets it manually
-- with `SET request.jwt.claim.sub = '<uuid>'` before querying.
CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID AS $$
  SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::UUID;
$$ LANGUAGE sql STABLE;

-- A non-superuser, non-BYPASSRLS role standing in for Supabase's
-- `authenticated` role. RLS is silently skipped for superusers and
-- table owners, so testing as the migration-applying role would prove
-- nothing -- every RLS check in this repo's local tests must run as
-- this role.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOBYPASSRLS;
  END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA auth TO authenticated;
