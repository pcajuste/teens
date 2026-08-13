-- Adds the "structured_qa" feedback_format to Insight & Feedback
-- (issue #52: bounded, brand-defined short-answer questions -- the
-- lower-risk deferred format shipped ahead of fully open free text).
-- See 20260823090000_brand_content_templates.sql for the base tables;
-- this migration only extends them.

-- ──────────────────────────────────────────────────────────────────
-- Campaign: allow structured_qa + a brand-authored question list
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.insight_feedback_campaigns
  DROP CONSTRAINT insight_feedback_campaigns_feedback_format_check;

ALTER TABLE public.insight_feedback_campaigns
  ADD CONSTRAINT insight_feedback_campaigns_feedback_format_check
    CHECK (feedback_format IN ('rating_scale', 'structured_qa'));

-- Ordered, brand-authored at creation, immutable after: [{"id": "q1",
-- "prompt": "..."}]. Capped at 8 -- bounds both the deanonymization
-- surface (fewer free-text fields per teen) and the per-response
-- admin review burden introduced below.
ALTER TABLE public.insight_feedback_campaigns
  ADD COLUMN qa_questions JSONB NOT NULL DEFAULT '[]';

ALTER TABLE public.insight_feedback_campaigns
  ADD CONSTRAINT insight_campaigns_structured_qa_has_questions
    CHECK (
      feedback_format <> 'structured_qa'
      OR (jsonb_typeof(qa_questions) = 'array' AND jsonb_array_length(qa_questions) BETWEEN 1 AND 8)
    );

-- ──────────────────────────────────────────────────────────────────
-- Responses: per-response moderation, mirroring the campaign-level
-- moderation_status/reviewed_by/reviewed_at/rejection_reason pattern
-- above but applied per-row. rating_scale rows stay 'approved'
-- immediately (a 1-5 score carries no PII risk); structured_qa rows
-- start 'pending_review' and are gated by a new admin queue -- no
-- response is ever auto-cleared straight to the brand. Enforced in
-- app code (insight_feedback_repository.submit_response), not a
-- trigger, so a scrubber bug can't silently flip status.
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.insight_feedback_responses
  ADD COLUMN qa_answers        JSONB,        -- [{"question_id": "...", "answer_text": "..."}], NULL for rating_scale
  ADD COLUMN moderation_status content_moderation_status NOT NULL DEFAULT 'approved',
  ADD COLUMN reviewed_by       UUID REFERENCES public.users(id),
  ADD COLUMN reviewed_at       TIMESTAMPTZ,
  ADD COLUMN rejection_reason  TEXT,
  -- Regex/keyword PII-scrubber output, kept for reviewer context and
  -- audit only -- never itself a source of auto-clearance.
  ADD COLUMN scrub_flags       JSONB NOT NULL DEFAULT '[]';

ALTER TABLE public.insight_feedback_responses
  ADD CONSTRAINT insight_responses_qa_shape
    CHECK (qa_answers IS NULL OR jsonb_typeof(qa_answers) = 'array');

CREATE INDEX idx_insight_responses_moderation_queue
  ON public.insight_feedback_responses (moderation_status) WHERE moderation_status = 'pending_review';

-- No RLS changes: insight_feedback_responses already has no brand
-- SELECT policy (brand reads exclusively via the service-role
-- repository path -- see the base migration's comment above the RLS
-- section); talent's existing own-row policy is unaffected by these
-- additional columns.
