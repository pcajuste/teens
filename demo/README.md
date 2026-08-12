# /demo

Empty scaffold. This directory will hold the seed data and script that power
the **public-facing demo experiences** — the interactive rep demo
(`apps/web/app/(marketing)/demo/rep/`, Prompt 6A) and the recruiter
preview / brand sales page (`apps/web/app/(marketing)/demo/recruiter/`,
`.../demo/brand/`, Prompt 12A) — plus the marketing/investor/sales demo more
generally.

## Rules for this directory

- **Strictly separate from Prompt 2's dev-fixture seed script.** That script
  seeds a local Supabase instance for development/testing and is not public.
  This directory seeds the public demo surfaces that anyone can load without
  authentication.
- **Never contains anything that looks like a real minor's data.** Every demo
  rep, brand, and campaign must be unmistakably fictional — invented names,
  invented schools, no resemblance to a real person or company.
- **Must stay stable release-over-release.** Demo links are shared externally
  (sales, investors, marketing). Do not restructure or remove existing demo
  records in a way that breaks a previously-shared link or state.

No seed data exists yet — this scaffold is created ahead of Prompt 6A/12A per
Prompt 1's deliverables.
