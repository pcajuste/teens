import { test, expect, type ConsoleMessage, type Page } from "@playwright/test";

// Smoke coverage for the two auth pages that are reachable without an
// authenticated Supabase session (see app/(rep)/rep-gate.tsx's
// PUBLIC_PATHS). Every other /rep/* route is gated behind RepGate and
// redirects to /rep/login when there is no session -- exercising them
// meaningfully requires a real Supabase/Postgres backend running
// alongside this suite, which is a separate follow-up (the demo portal
// at /demo/rep, covered in demo-rep-portal.spec.ts, has no such
// dependency and is fully covered here).

function collectPageErrors(page: Page) {
  const errors: string[] = [];
  const consoleErrors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("console", (msg: ConsoleMessage) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  return { errors, consoleErrors };
}

async function expectNoErrorOverlay(page: Page) {
  // Next.js dev/prod error overlay root -- if this is attached, the page
  // crashed client-side.
  await expect(page.locator("nextjs-portal")).toHaveCount(0);
}

test.describe("/rep/signup", () => {
  test("loads and renders the signup form without a client-side exception", async ({ page }) => {
    const { errors, consoleErrors } = collectPageErrors(page);

    await page.goto("/rep/signup");

    await expect(page.getByRole("heading", { name: "Create your Teenure account" })).toBeVisible();
    await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Date of birth")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign up" })).toBeVisible();

    await expectNoErrorOverlay(page);
    expect(errors, `Unhandled page errors: ${errors.join("; ")}`).toEqual([]);
    expect(consoleErrors, `Console errors: ${consoleErrors.join("; ")}`).toEqual([]);
  });
});

test.describe("/rep/login", () => {
  test("loads and renders the login form without a client-side exception", async ({ page }) => {
    const { errors, consoleErrors } = collectPageErrors(page);

    await page.goto("/rep/login");

    await expect(page.getByRole("heading", { name: "Sign in to Teenure" })).toBeVisible();
    await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();

    await expectNoErrorOverlay(page);
    expect(errors, `Unhandled page errors: ${errors.join("; ")}`).toEqual([]);
    expect(consoleErrors, `Console errors: ${consoleErrors.join("; ")}`).toEqual([]);
  });
});

test.describe("gated /rep routes", () => {
  test("visiting the dashboard without a session redirects to /rep/login", async ({ page }) => {
    await page.goto("/rep");
    await expect(page).toHaveURL(/\/rep\/login$/);
    await expect(page.getByRole("heading", { name: "Sign in to Teenure" })).toBeVisible();
  });
});
