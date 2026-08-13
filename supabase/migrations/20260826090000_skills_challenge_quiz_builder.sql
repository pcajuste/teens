-- ──────────────────────────────────────────────────────────────────
-- Interactive quiz builder for Skills Challenges (Build Prompt 8I,
-- step 5a -- issue #51). Last of the five 8I templates, sequenced
-- last because it needs the most moderation infrastructure: per
-- Section 5 of docs/Teenure_Brand_Content_Templates.md, "quiz
-- questions and scoring logic should be submitted for review, not
-- just the wrapper" -- so quiz_questions rides through the exact same
-- moderation_status gate the rest of the Skills Challenge content
-- layer already uses (20260823090000_brand_content_templates.sql),
-- rather than a separate approval path.
--
-- quiz_questions stores the RAW content, including each question's
-- correct_index -- same shape and same never-serialize-directly rule
-- as learning_modules.content_blocks
-- (20260821090000_learning_modules.sql / strip_correct_index in
-- app/repositories/challenges_repository.py). No RLS change is needed
-- beyond what challenges/challenge_submissions already enforce: the
-- brand-owns-challenges and talent-owns-submissions policies already
-- gate every row this migration touches; the answer-key leak surface
-- is closed at the application/serializer layer, not RLS, matching
-- brand_note's precedent on this same table.
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.challenges
  ADD COLUMN quiz_questions JSONB NOT NULL DEFAULT '[]';
  -- [{"question": "...", "options": ["...","...","...","..."], "correct_index": 0}, ...]
  -- Empty array means "no quiz attached" -- quiz remains optional per
  -- Section 2B ("Optional: interactive quiz or assessment").

ALTER TABLE public.challenge_submissions
  ADD COLUMN quiz_answers    JSONB,               -- talent's submitted answers: [talent_answer_index, ...] -- null until attempted
  ADD COLUMN quiz_score      INTEGER,              -- number of correct answers, set once on first (only) attempt
  ADD COLUMN quiz_total      INTEGER,              -- len(quiz_questions) at attempt time, so a later brand edit can't retroactively change a talent's own historical score
  ADD COLUMN quiz_answered_at TIMESTAMPTZ;

-- No data collection beyond what the quiz itself needs (Section 5:
-- "no stealth lead-gen") -- quiz_answers stores only answer indices,
-- never free text, and there is no column here for anything beyond
-- the scoring inputs themselves.
