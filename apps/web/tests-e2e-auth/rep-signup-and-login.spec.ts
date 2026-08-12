import { test, expect } from "@playwright/test";

// Real signup -> real GoTrue login, end to end, against a live
// apps/api + local Supabase Auth stack (see playwright.auth.config.ts
// for the preconditions this suite assumes). Unlike
// demo-rep-portal.spec.ts, this suite genuinely creates auth.users
// rows and public.users rows -- each test uses a unique email so
// repeated runs never collide on "already registered".
function uniqueEmail(label: string): string {
  return `e2e-${label}-${test.info().workerIndex}-${test.info().repeatEachIndex}-${Math.random()
    .toString(36)
    .slice(2)}@example.com`;
}

// 2005-06-15 -> comfortably 18+ as of any run of this suite for the
// foreseeable future, so signup activates immediately with no
// parental-consent branch to navigate around.
const ADULT_DOB = "2005-06-15";
const PASSWORD = "SuperSecret123!";

test.describe("rep signup", () => {
  test("creates a real account and lands on onboarding", async ({ page }) => {
    const email = uniqueEmail("signup");

    await page.goto("/rep/signup");
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByLabel("Date of birth").fill(ADULT_DOB);
    await page.getByRole("button", { name: "Sign up" }).click();

    await expect(page).toHaveURL(/\/rep\/onboarding$/, { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Set up your profile" })).toBeVisible();
  });

  test("rejects a duplicate email with a real backend error, not a client-side guess", async ({ page }) => {
    const email = uniqueEmail("dup");

    await page.goto("/rep/signup");
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByLabel("Date of birth").fill(ADULT_DOB);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/rep\/onboarding$/, { timeout: 15_000 });

    await page.goto("/rep/signup");
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByLabel("Date of birth").fill(ADULT_DOB);
    await page.getByRole("button", { name: "Sign up" }).click();

    await expect(page.getByText(`${email} is already registered`)).toBeVisible({ timeout: 15_000 });
    await expect(page).toHaveURL(/\/rep\/signup$/);
  });
});

test.describe("rep login", () => {
  test("an existing account can sign in and reach the dashboard", async ({ page }) => {
    const email = uniqueEmail("login");

    await page.goto("/rep/signup");
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByLabel("Date of birth").fill(ADULT_DOB);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/rep\/onboarding$/, { timeout: 15_000 });

    // Fresh, signed-out context: signup's own auto-sign-in proves
    // nothing about the separate /rep/login code path.
    await page.context().clearCookies();
    await page.evaluate(() => localStorage.clear());

    await page.goto("/rep/login");
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL(/\/rep(\/onboarding)?$/, { timeout: 15_000 });
  });

  test("wrong password is rejected with a real GoTrue error", async ({ page }) => {
    const email = uniqueEmail("badpw");

    await page.goto("/rep/signup");
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByLabel("Date of birth").fill(ADULT_DOB);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page).toHaveURL(/\/rep\/onboarding$/, { timeout: 15_000 });

    await page.context().clearCookies();
    await page.evaluate(() => localStorage.clear());

    await page.goto("/rep/login");
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill("wrong-password-entirely");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL(/\/rep\/login$/);
    await expect(page.locator("p.text-destructive")).toBeVisible({ timeout: 10_000 });
  });
});
