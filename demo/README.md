# /demo

Seed data and loader scripts for Teenure's public-facing demo
experiences — the rep demo (Prompt 6A), the recruiter preview and brand
sales page (Prompt 12A), and by extension the marketing site, investor
presentations, and sales calls that reuse the same data.

This is a separate concern from `scripts/seed_dev.sql` (dev-only
fixture data for local development/testing against a fresh local
Postgres):

- `scripts/seed_dev.sql` — one user per role, minimal, disposable, safe
  to reset on every local rebuild.
- `demo/` — public-facing, must stay stable release-over-release (demo
  links shouldn't break), and every record must be unmistakably
  fictional on inspection (invented names, invented schools) — this is
  a platform for minors, so "no PII" alone is not a sufficient bar.

## Status

Empty scaffold as of Prompt 1. No seed data yet — deliberately: the
demo needs to look realistic against business logic (profile
completeness scoring, campaign state machine, earnings bucketing) that
doesn't exist until later phases. Populating this now would mean
rebuilding it once that logic lands.

- Rep-side seed data + loader: built in Prompt 6A, once Prompt 5's
  profile/campaign/earnings logic exists to seed against.
- Recruiter-facing search data + optional multi-year earnings
  extension: built in Prompt 12A, reusing Prompt 11's real search
  endpoint and Prompt 10's real payout engine rather than fabricating
  either.

Never commit anything here that looks like a real minor's data, even
if fabricated to look realistic.
