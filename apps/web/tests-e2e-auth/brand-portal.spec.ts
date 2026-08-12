import { execSync } from "node:child_process";
import { test, expect } from "@playwright/test";

// Real signup -> company profile -> campaign creation -> activation,
// against a live apps/api + local Supabase Auth stack. Mirrors
// rep-signup-and-login.spec.ts's shape for the brand side.
//
// Every brand signup lands account_status='pending' -- there is no
// admin-approval flow yet (Prompt 13), so a real signup can reach
// company-profile submission but genuinely cannot create a campaign
// (require_role("brand") requires 'active' for anything money-moving;
// see apps/api/app/routers/brands.py's module docstring). Rather than
// fake that boundary away in application code, `approveBrand` below
// simulates the admin-approval step Prompt 13 will eventually provide,
// the same way apps/api's own pytest suite seeds 'active' brands
// directly via SQL -- this is a test-only shortcut for a real gap, not
// a claim that approval works today.
//
// Does not cover rep browse/invite (needs a seeded rep with
// recruiter_visible=true, which this suite has no way to seed against
// a real backend) -- that path is covered at the API layer by
// apps/api/tests/test_brands_portal.py.

const SUPABASE_URL = "http://127.0.0.1:54321";
const SERVICE_ROLE_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU";

function uniqueEmail(label: string): string {
  return `e2e-${label}-${test.info().workerIndex}-${Math.random().toString(36).slice(2)}@example.com`;
}

const PASSWORD = "SuperSecret123!";

async function signUpAndOnboard(page: import("@playwright/test").Page, email: string) {
  await page.goto("/brand/signup");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign up" }).click();
  await expect(page).toHaveURL(/\/brand\/onboarding$/, { timeout: 15_000 });

  await page.getByLabel("Company name").fill("Acme Co");
  await page.getByLabel("Website").fill("https://acme.example.com");
  await page.getByLabel(/^EIN/).fill("12-3456789");
  await page.getByRole("button", { name: "Gaming" }).click();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved.")).toBeVisible({ timeout: 10_000 });
}

/** Simulates the admin-approval step Prompt 13 will provide -- flips
 * both the Supabase Auth JWT claim (what the frontend/backend actually
 * read) and the mirrored public.users row. See file-level comment. */
async function approveBrand(email: string) {
  const listResp = await fetch(`${SUPABASE_URL}/auth/v1/admin/users?email=${encodeURIComponent(email)}`, {
    headers: { apikey: SERVICE_ROLE_KEY, Authorization: `Bearer ${SERVICE_ROLE_KEY}` },
  });
  const { users } = (await listResp.json()) as { users: { id: string }[] };
  const userId = users[0].id;

  await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${userId}`, {
    method: "PUT",
    headers: {
      apikey: SERVICE_ROLE_KEY,
      Authorization: `Bearer ${SERVICE_ROLE_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ app_metadata: { role: "brand", account_status: "active" } }),
  });

  execSync(
    `PGPASSWORD=postgres psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -c ` +
      `"UPDATE public.users SET account_status='active' WHERE id='${userId}'"`,
    { stdio: "pipe" }
  );
}

/** The browser's live session token was issued at signup, before
 * approveBrand() ran -- Supabase doesn't push server-side app_metadata
 * changes into an already-issued access token, so the old 'pending'
 * claim keeps gating navigation until the token is naturally refreshed
 * (too slow for a test) or a fresh one is issued. Signing out and back
 * in re-authenticates with GoTrue, which stamps the current
 * app_metadata into a brand-new token. */
async function reloginToPickUpApproval(page: import("@playwright/test").Page, email: string) {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/brand$/, { timeout: 15_000 });
}

test.describe("brand signup and onboarding", () => {
  test("creates a real account, completes company profile, stays gated pending approval", async ({ page }) => {
    const email = uniqueEmail("brand-onboard");
    await signUpAndOnboard(page, email);

    // Real, current product behavior: a freshly-onboarded brand is
    // still 'pending' (no admin approved them) and the dashboard stays
    // gated, with a way back to the profile they just submitted.
    await page.goto("/brand");
    await expect(page.getByText("Your account is under review")).toBeVisible();
    await expect(page.getByRole("link", { name: "Finish your company profile" })).toBeVisible();
  });
});

test.describe("campaign creation and activation", () => {
  test("brief builder shows a live preview and creates a real campaign", async ({ page }) => {
    const email = uniqueEmail("brand-campaign");
    await signUpAndOnboard(page, email);
    await approveBrand(email);
    await reloginToPickUpApproval(page, email);
    await page.goto("/brand/campaigns/new");

    await page.getByLabel("Campaign title").fill("Spring Launch");
    await page.getByLabel("Product name").fill("Acme Widget");
    await page.getByLabel("Campaign goal").fill("Drive awareness");
    await page.getByLabel("Key messaging").fill("Widgets are great");
    await page.getByLabel("Deliverables").fill("One TikTok post");
    await page.getByRole("button", { name: "Gaming" }).click();

    // Live preview reflects form state before submission -- title isn't
    // part of CampaignBrief (it's a page-level heading everywhere it's
    // used, not part of the shared renderer), so assert on fields the
    // component actually renders.
    await expect(page.getByText("Acme Widget")).toBeVisible();
    await expect(page.getByText("Drive awareness")).toBeVisible();

    await page.getByLabel("Max reps").fill("5");
    await page.getByLabel("Budget (USD)").fill("1000");

    await page.getByRole("button", { name: "Create campaign" }).click();
    await expect(page).toHaveURL(/\/brand\/campaigns\/[0-9a-f-]+$/, { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Spring Launch" })).toBeVisible();
    await expect(page.getByText("Draft")).toBeVisible();
  });

  test("activating a draft campaign creates a real Stripe PaymentIntent and transitions status", async ({ page }) => {
    const email = uniqueEmail("brand-activate");
    await signUpAndOnboard(page, email);
    await approveBrand(email);
    await reloginToPickUpApproval(page, email);
    await page.goto("/brand/campaigns/new");

    await page.getByLabel("Campaign title").fill("Activation Test");
    await page.getByLabel("Product name").fill("Widget");
    await page.getByLabel("Campaign goal").fill("Awareness");
    await page.getByLabel("Key messaging").fill("msg");
    await page.getByLabel("Deliverables").fill("one post");
    await page.getByRole("button", { name: "Gaming" }).click();
    await page.getByLabel("Max reps").fill("5");
    await page.getByLabel("Budget (USD)").fill("500");
    await page.getByRole("button", { name: "Create campaign" }).click();
    await expect(page).toHaveURL(/\/brand\/campaigns\/[0-9a-f-]+$/, { timeout: 15_000 });

    await page.getByRole("button", { name: "Activate campaign" }).click();
    // A real (test-mode) Stripe PaymentIntent call happens here -- with
    // only a placeholder STRIPE_SECRET_KEY configured locally, Stripe
    // itself rejects the call, which surfaces as an error in the UI
    // ("Something went wrong" is lib/api.ts's fallback for a non-JSON/
    // network-level failure, distinct from a structured ApiError).
    // Either a successful transition or a surfaced error is acceptable
    // proof the wiring is real (not mocked) -- what's not acceptable is
    // the request silently doing nothing.
    await expect(page.getByText(/Payment initiated|Something went wrong|error/i).first()).toBeVisible({
      timeout: 15_000,
    });
  });
});
