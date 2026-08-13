import { execSync } from "node:child_process";
import { test, expect, type Page } from "@playwright/test";

// Walks each portal's NAV array (talent-shell.tsx / brand-shell.tsx /
// recruiter-shell.tsx) and asserts every href actually renders instead of
// a 404 or a crashed page. Filed as apps.web e2e coverage for #45 ("do all
// the surfaces we think exist actually exist and get reached").
//
// Admin and Parent are intentionally NOT covered here: admin has no
// self-serve signup (accounts are provisioned out-of-band, Prompt 13's own
// admin-approval flow doesn't exist yet either) and parent accounts are
// created via a magic-link token tied to a talent's parent_email, not
// password auth -- both need their own fixture strategy, tracked
// separately rather than faked here. See the follow-up issue linked from
// #45.

const SUPABASE_URL = "http://127.0.0.1:54321";
const SERVICE_ROLE_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU";
const PASSWORD = "SuperSecret123!";

function uniqueEmail(label: string): string {
  return `e2e-navsweep-${label}-${test.info().workerIndex}-${Math.random().toString(36).slice(2)}@example.com`;
}

/** Shared with brand-portal.spec.ts's approveBrand -- flips both the
 * Supabase Auth JWT claim and the mirrored public.users row, then a fresh
 * login picks up the new claim (server-side app_metadata changes don't
 * retroactively update an already-issued access token). */
async function setAccountStatus(email: string, role: string, accountStatus: string) {
  const listResp = await fetch(
    `${SUPABASE_URL}/auth/v1/admin/users?email=${encodeURIComponent(email)}`,
    { headers: { apikey: SERVICE_ROLE_KEY, Authorization: `Bearer ${SERVICE_ROLE_KEY}` } },
  );
  const { users } = (await listResp.json()) as { users: { id: string }[] };
  const userId = users[0].id;

  await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${userId}`, {
    method: "PUT",
    headers: {
      apikey: SERVICE_ROLE_KEY,
      Authorization: `Bearer ${SERVICE_ROLE_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ app_metadata: { role, account_status: accountStatus } }),
  });

  execSync(
    `PGPASSWORD=postgres psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -c ` +
      `"UPDATE public.users SET account_status='${accountStatus}' WHERE id='${userId}'"`,
    { stdio: "pipe" },
  );
}

async function relogin(page: Page, email: string, landingUrlPattern: RegExp) {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(landingUrlPattern, { timeout: 15_000 });
}

/** Visits every nav href and asserts it renders -- no 404, no crashed
 * page. Doesn't assert on page *content* beyond that, since each page's
 * actual content is covered by its own dedicated tests elsewhere. */
async function sweepNav(page: Page, hrefs: string[]) {
  for (const href of hrefs) {
    const response = await page.goto(href);
    expect(response?.ok(), `${href} returned ${response?.status()}`).toBeTruthy();
    await expect(
      page.getByText("This page could not be found"),
      `${href} rendered a 404`,
    ).toHaveCount(0);
    await expect(
      page.getByText("Application error"),
      `${href} crashed`,
    ).toHaveCount(0);
  }
}

const ADULT_DOB = "2005-06-15";

test.describe("nav sweep", () => {
  test("every talent NAV href renders", async ({ page }) => {
    const email = uniqueEmail("talent");
    await page.goto("/talent/signup");
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByLabel("Date of birth").fill(ADULT_DOB);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/talent\/onboarding$/, { timeout: 15_000 });

    await sweepNav(page, [
      "/talent",
      "/talent/learning",
      "/talent/scholarships",
      "/talent/insight-feedback",
      "/talent/profile-preview",
    ]);
  });

  test("every brand NAV href renders", async ({ page }) => {
    const email = uniqueEmail("brand");
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

    await setAccountStatus(email, "brand", "active");
    await relogin(page, email, /\/brand$/);

    await sweepNav(page, [
      "/brand",
      "/brand/challenges",
      "/brand/scholarships",
      "/brand/insight-feedback",
      "/brand/exclusivity",
      "/brand/company-profile",
      "/brand/onboarding",
    ]);
  });

  test("every recruiter NAV href renders", async ({ page }) => {
    const email = uniqueEmail("recruiter");
    await page.goto("/recruiter/signup");
    await page.getByLabel("Institution email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/recruiter\/profile$/, { timeout: 15_000 });

    // Recruiter activation needs admin approval AND an active
    // subscription (dual gate, see (recruiter)/layout.tsx) -- routing a
    // real Stripe Checkout through this sweep is out of scope for "does
    // the page render", so the DB is flipped directly the same way
    // approveBrand does for the brand suite.
    await setAccountStatus(email, "recruiter", "active");
    await relogin(page, email, /\/recruiter$/);

    await sweepNav(page, [
      "/recruiter",
      "/recruiter/saved",
      "/recruiter/messages",
      "/recruiter/subscription",
      "/recruiter/profile",
    ]);
  });
});
