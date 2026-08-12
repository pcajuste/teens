-- ──────────────────────────────────────────────────────────────────
-- Extensions + local auth.users / auth.uid() shim
-- ──────────────────────────────────────────────────────────────────
-- On a real Supabase project, the `auth` schema (auth.users, auth.uid(),
-- auth.jwt(), auth.role()) is provided by Supabase's GoTrue + Postgres
-- extensions and must NOT be created by application migrations. This
-- file exists ONLY so this migration set can be applied and RLS-tested
-- against a bare local Postgres container (no Supabase CLI / GoTrue
-- running locally — see scripts/local-dev/docker-compose.yml).
--
-- On an actual Supabase project, skip this file entirely; auth.users
-- and auth.uid() already exist and this file would conflict with them.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT
);

-- Mirrors Supabase's auth.uid() helper: reads the "sub" claim out of a
-- JWT that PostgREST/Supabase would normally set via
-- `SET LOCAL request.jwt.claims`. For local testing we set the same
-- GUC by hand (see scripts/local-dev/test_rls.sql) with:
--   SET LOCAL request.jwt.claims = '{"sub": "<uuid>", "role": "authenticated"}';
CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID
LANGUAGE sql STABLE
AS $$
  SELECT (NULLIF(current_setting('request.jwt.claims', true), '')::json->>'sub')::uuid;
$$;

CREATE OR REPLACE FUNCTION auth.role() RETURNS TEXT
LANGUAGE sql STABLE
AS $$
  SELECT NULLIF(current_setting('request.jwt.claims', true), '')::json->>'role';
$$;
