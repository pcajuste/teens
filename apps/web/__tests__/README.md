# Frontend test coverage (Build Prompt 16, deliverable 4)

Run with `pnpm test` (Vitest + React Testing Library, jsdom).

| Requirement | Test file | Status |
|---|---|---|
| FTC checkbox gate | `campaign-participation.test.tsx` | Covered |
| Credit-spend confirmation prompt | `credit-confirm-dialog.test.tsx` | Covered |
| Age-gate / pending-consent screen | `auth-gate-pending-consent.test.tsx` | Covered |
| Parent-approval-pending state in rep campaign view | `campaign-participation.test.tsx` | Covered |
| Parent portal approve/block actions | `parent-approve-block.test.tsx` | Covered |
| Available-campaigns panel excludes parent-blocked category | `available-campaigns-blocked-category.test.tsx` | Covered |
| Rep cannot submit a sequence-required milestone before prior milestones are confirmed | — | **Not applicable — no code exists to test.** See `docs/test-coverage-report.md`: Prompt 8B (Performance Milestone Payments) was never implemented anywhere in this codebase (backend or frontend) — it exists only as a spec section. There is no milestone submission UI, so there is nothing to disable/assert against. This should be closed once Prompt 8B actually ships, not by this testing pass. |
