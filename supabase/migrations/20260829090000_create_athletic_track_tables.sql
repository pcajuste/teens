-- Migration: create_athletic_track_tables
BEGIN;

-- Sport-specific talent profile (D3: typed validation at API layer, JSONB storage)
CREATE TABLE public.sport_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    talent_id       UUID NOT NULL REFERENCES public.talent_profiles(id) ON DELETE CASCADE,
    sport           TEXT NOT NULL,
    positions       TEXT[] NOT NULL DEFAULT '{}',
    gpa             NUMERIC(3,2),
    hudl_url        TEXT,
    maxpreps_url    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (talent_id, sport)
);

-- Athletic season records
-- token columns REMOVED per D7 — tokens live in coach_attestation_tokens
-- achievements REMOVED per D9 — stored in sport_stats JSONB at MVP
CREATE TABLE public.athletic_seasons (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    talent_id                   UUID NOT NULL REFERENCES public.talent_profiles(id) ON DELETE CASCADE,
    sport                       TEXT NOT NULL,
    season_year                 INTEGER NOT NULL,
    season_type                 TEXT NOT NULL CHECK (season_type IN (
                                    'high_school', 'travel', 'club', 'aau', 'other'
                                )),
    team_name                   TEXT NOT NULL,
    level                       TEXT NOT NULL CHECK (level IN (
                                    'varsity', 'jv', 'freshman', 'travel', 'other'
                                )),
    -- sport_stats includes achievements at MVP:
    -- { "passing_yards": 2400, "achievements": [{"title": "All-Conference", ...}] }
    sport_stats                 JSONB NOT NULL DEFAULT '{}',
    coach_name                  TEXT,
    coach_email                 TEXT,
    coach_attestation_status    TEXT NOT NULL DEFAULT 'not_requested'
                                CHECK (coach_attestation_status IN (
                                    'not_requested', 'requested', 'attested',
                                    'declined', 'expired'
                                )),
    coach_attested_at           TIMESTAMPTZ,
    admin_verified              BOOLEAN NOT NULL DEFAULT FALSE,
    admin_verified_at           TIMESTAMPTZ,
    admin_verified_by           TEXT,
    -- D6: intelligence pipeline trigger
    intelligence_event_written_at  TIMESTAMPTZ,
    status                      TEXT NOT NULL DEFAULT 'draft'
                                CHECK (status IN (
                                    'draft', 'pending_attestation',
                                    'attested', 'verified'
                                )),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_athletic_seasons_talent
    ON public.athletic_seasons (talent_id, season_year DESC);

-- D6: intelligence pipeline index
CREATE INDEX idx_athletic_seasons_pending_intelligence
    ON public.athletic_seasons (id)
    WHERE status IN ('attested', 'verified')
      AND intelligence_event_written_at IS NULL;

-- D7: Separate tokens table — mirrors parent_auth_tokens pattern exactly
CREATE TABLE public.coach_attestation_tokens (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    athletic_season_id  UUID NOT NULL REFERENCES public.athletic_seasons(id) ON DELETE CASCADE,
    token               TEXT NOT NULL UNIQUE,
    coach_email         TEXT NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL,
    used_at             TIMESTAMPTZ,
    -- D8: superseded_at tracks when a new token was issued before this expired
    superseded_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_coach_attestation_tokens_season
    ON public.coach_attestation_tokens (athletic_season_id)
    WHERE used_at IS NULL AND superseded_at IS NULL;

-- D5: Admin-managed NIL state eligibility table
-- Seeds with current state map; admin updates when laws change
-- 45 states + DC allow high school NIL as of late 2025
CREATE TABLE public.nil_state_rules (
    state               TEXT PRIMARY KEY,  -- two-letter abbreviation
    nil_eligible        BOOLEAN NOT NULL,
    notes               TEXT,
    effective_date      DATE NOT NULL,
    last_updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed the 45 eligible states + DC (as of late 2025)
-- Non-eligible states: AL, ID, NY, OH, UT, WI (6 states — update when laws change)
INSERT INTO public.nil_state_rules (state, nil_eligible, notes, effective_date) VALUES
    ('AK', TRUE,  NULL, '2023-01-01'),
    ('AR', TRUE,  NULL, '2021-07-01'),
    ('AZ', TRUE,  NULL, '2021-07-01'),
    ('CA', TRUE,  NULL, '2021-07-01'),
    ('CO', TRUE,  NULL, '2021-07-01'),
    ('CT', TRUE,  NULL, '2021-07-01'),
    ('DC', TRUE,  NULL, '2021-07-01'),
    ('DE', TRUE,  NULL, '2021-07-01'),
    ('FL', TRUE,  'Updated 2024 FHSAA Bylaw 9.9', '2024-07-01'),
    ('GA', TRUE,  NULL, '2021-07-01'),
    ('HI', TRUE,  NULL, '2022-01-01'),
    ('IA', TRUE,  NULL, '2022-07-01'),
    ('IL', TRUE,  NULL, '2021-07-01'),
    ('IN', TRUE,  NULL, '2022-07-01'),
    ('KS', TRUE,  NULL, '2022-07-01'),
    ('KY', TRUE,  'No school name/logo in NIL content', '2022-01-01'),
    ('LA', TRUE,  NULL, '2021-07-01'),
    ('MA', TRUE,  NULL, '2022-07-01'),
    ('MD', TRUE,  NULL, '2021-07-01'),
    ('ME', TRUE,  NULL, '2022-01-01'),
    ('MI', TRUE,  NULL, '2022-07-01'),
    ('MN', TRUE,  NULL, '2022-07-01'),
    ('MO', TRUE,  NULL, '2022-07-01'),
    ('MS', TRUE,  NULL, '2022-07-01'),
    ('MT', TRUE,  NULL, '2022-07-01'),
    ('NC', TRUE,  NULL, '2021-07-01'),
    ('ND', TRUE,  NULL, '2022-07-01'),
    ('NE', TRUE,  NULL, '2022-07-01'),
    ('NH', TRUE,  NULL, '2022-07-01'),
    ('NJ', TRUE,  NULL, '2021-07-01'),
    ('NM', TRUE,  NULL, '2022-07-01'),
    ('NV', TRUE,  NULL, '2022-07-01'),
    ('OR', TRUE,  NULL, '2021-07-01'),
    ('PA', TRUE,  NULL, '2022-07-01'),
    ('RI', TRUE,  NULL, '2022-07-01'),
    ('SC', TRUE,  NULL, '2022-07-01'),
    ('SD', TRUE,  NULL, '2022-07-01'),
    ('TN', TRUE,  NULL, '2022-07-01'),
    ('TX', TRUE,  NULL, '2021-07-01'),
    ('VA', TRUE,  NULL, '2021-07-01'),
    ('VT', TRUE,  NULL, '2022-07-01'),
    ('WA', TRUE,  NULL, '2022-07-01'),
    ('WV', TRUE,  NULL, '2022-07-01'),
    ('WY', TRUE,  NULL, '2022-07-01'),
    ('AL', FALSE, 'No state NIL policy for high school athletes', '2025-01-01'),
    ('ID', FALSE, 'No state NIL policy for high school athletes', '2025-01-01'),
    ('NY', FALSE, 'NYSPHSAA prohibits NIL for high school athletes', '2025-01-01'),
    ('OH', FALSE, 'OHSAA prohibits NIL for high school athletes', '2025-01-01'),
    ('UT', FALSE, 'No state NIL policy for high school athletes', '2025-01-01'),
    ('WI', FALSE, 'WIAA prohibits NIL for high school athletes', '2025-01-01')
ON CONFLICT (state) DO NOTHING;

-- Talent NIL eligibility records (links talent to their state's rules)
CREATE TABLE public.nil_eligibility_records (
    id                                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    talent_id                               UUID NOT NULL REFERENCES public.talent_profiles(id) ON DELETE CASCADE,
    state                                   TEXT NOT NULL REFERENCES public.nil_state_rules(state),
    nil_eligible_in_state                   BOOLEAN NOT NULL,
    school_association_rules_acknowledged   BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_at                         TIMESTAMPTZ,
    eligibility_checked_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (talent_id, state)
);

-- D4: College coach sport interest on recruiter_profiles
ALTER TABLE public.recruiter_profiles
    ADD COLUMN sports_of_interest TEXT[];
-- NULL means "all sports" or "employer-type, no sport filter"

-- RLS on all new tables
ALTER TABLE public.sport_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.athletic_seasons ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coach_attestation_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nil_eligibility_records ENABLE ROW LEVEL SECURITY;

CREATE POLICY "talent_owns_sport_profiles"
    ON public.sport_profiles FOR ALL
    USING (talent_id IN (SELECT id FROM public.talent_profiles WHERE user_id = auth.uid()));

CREATE POLICY "talent_owns_athletic_seasons"
    ON public.athletic_seasons FOR ALL
    USING (talent_id IN (SELECT id FROM public.talent_profiles WHERE user_id = auth.uid()));

CREATE POLICY "talent_owns_nil_records"
    ON public.nil_eligibility_records FOR ALL
    USING (talent_id IN (SELECT id FROM public.talent_profiles WHERE user_id = auth.uid()));

-- Coach attestation tokens: no direct talent access (opaque, server-side only)
-- Admin uses service role. Talent cannot read their own tokens (no enumeration risk).

-- Recruiters see attested/verified seasons on visible talent profiles
CREATE POLICY "recruiter_reads_attested_seasons"
    ON public.athletic_seasons FOR SELECT
    USING (
        status IN ('attested', 'verified')
        AND talent_id IN (
            SELECT id FROM public.talent_profiles WHERE recruiter_visible = TRUE
        )
        AND EXISTS (
            SELECT 1 FROM public.users WHERE id = auth.uid() AND role = 'recruiter'
        )
    );

COMMIT;
