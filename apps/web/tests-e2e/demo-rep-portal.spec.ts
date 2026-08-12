import { test, expect, type ConsoleMessage, type Page } from "@playwright/test";

// Smoke + behavioral coverage for the unauthenticated marketing demo at
// /demo/rep (Build Prompt 6A). Unlike the real (rep) portal, this route
// group has zero auth/session/backend dependency -- every assertion here
// can run against production-built static output with no live Supabase
// or FastAPI instance, so it's the most reliable E2E coverage available
// until a local Supabase/Postgres stack is wired into the test run.

const DEMO_REP_NAME = "Maya Chen";
const AVAILABLE_CAMPAIGN_ID = "demo-campaign-summit-trail";
const CONFIRMED_CAMPAIGN_ID = "demo-campaign-brightleaf-granola";
const AVAILABLE_CAMPAIGN_TITLE = "Summit Trail Spring Restock";
const CONFIRMED_CAMPAIGN_TITLE = "Brightleaf Granola Locker Room Launch";

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
  await expect(page.locator("nextjs-portal")).toHaveCount(0);
}

// Any request whose URL doesn't point at the Next.js server itself (same
// host:port the test is running against) is treated as a "backend" call
// for this suite's purposes -- the demo must never talk to anything else,
// since there's no live FastAPI/Supabase instance to talk to.
function collectForeignRequests(page: Page, baseURL: string) {
  const foreign: string[] = [];
  const base = new URL(baseURL);
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.protocol.startsWith("http") && url.origin !== base.origin) {
      foreign.push(req.url());
    }
  });
  return foreign;
}

test.describe("/demo/rep dashboard", () => {
  test("renders demo banner, profile, campaigns, and CTA with no backend calls", async ({ page, baseURL }) => {
    const { errors, consoleErrors } = collectPageErrors(page);
    const foreignRequests = collectForeignRequests(page, baseURL!);

    await page.goto("/demo/rep");

    await expect(page.getByText(/Demo — this is example data/i)).toBeVisible();
    await expect(page.getByRole("heading", { name: DEMO_REP_NAME })).toBeVisible();
    await expect(page.getByText(AVAILABLE_CAMPAIGN_TITLE)).toBeVisible();
    await expect(page.getByText(CONFIRMED_CAMPAIGN_TITLE)).toBeVisible();

    const cta = page.getByRole("link", { name: "Start building yours" });
    await expect(cta).toBeVisible();
    await expect(cta).toHaveAttribute("href", "/rep/signup");

    await expectNoErrorOverlay(page);
    expect(errors, `Unhandled page errors: ${errors.join("; ")}`).toEqual([]);
    expect(consoleErrors, `Console errors: ${consoleErrors.join("; ")}`).toEqual([]);
    expect(foreignRequests, `Unexpected non-local requests: ${foreignRequests.join("; ")}`).toEqual([]);
  });

  test("CTA navigates into the real signup flow, not a demo shortcut", async ({ page }) => {
    await page.goto("/demo/rep");
    await page.getByRole("link", { name: "Start building yours" }).click();
    await expect(page).toHaveURL(/\/rep\/signup$/);
    await expect(page.getByRole("heading", { name: "Create your Teenure account" })).toBeVisible();
  });
});

test.describe("/demo/rep/campaigns/[id] -- available campaign", () => {
  test("renders campaign detail with no apply/accept controls", async ({ page, baseURL }) => {
    const foreign = collectForeignRequests(page, baseURL!);

    await page.goto("/demo/rep");
    await page.getByRole("link").filter({ hasText: AVAILABLE_CAMPAIGN_TITLE }).click();
    await expect(page).toHaveURL(new RegExp(`/demo/rep/campaigns/${AVAILABLE_CAMPAIGN_ID}$`));

    await expect(page.getByRole("heading", { name: AVAILABLE_CAMPAIGN_TITLE })).toBeVisible();
    await expect(page.getByText(/Goal/i)).toBeVisible();
    await expect(page.getByText(/Deliverables/i)).toBeVisible();

    for (const label of [/^apply$/i, /^accept$/i, /^submit$/i, /^decline$/i, /^withdraw$/i]) {
      await expect(page.getByRole("button", { name: label })).toHaveCount(0);
    }

    const cta = page.getByRole("link", { name: "Start building yours" });
    await expect(cta).toHaveAttribute("href", "/rep/signup");
    expect(foreign, `Unexpected non-local requests: ${foreign.join("; ")}`).toEqual([]);
  });
});

test.describe("/demo/rep/campaigns/[id] -- confirmed campaign", () => {
  test("renders submission evidence and status tracker with no withdraw action", async ({ page, baseURL }) => {
    const foreign = collectForeignRequests(page, baseURL!);

    await page.goto(`/demo/rep/campaigns/${CONFIRMED_CAMPAIGN_ID}`);

    await expect(page.getByRole("heading", { name: CONFIRMED_CAMPAIGN_TITLE })).toBeVisible();
    await expect(page.getByText(/submitted work/i)).toBeVisible();
    await expect(page.getByText(/mock file, not a real upload/i).first()).toBeVisible();
    await expect(page.getByText(/confirmed/i).first()).toBeVisible();

    await expect(page.getByRole("button", { name: /withdraw/i })).toHaveCount(0);

    const cta = page.getByRole("link", { name: "Start building yours" });
    await expect(cta).toHaveAttribute("href", "/rep/signup");
    expect(foreign, `Unexpected non-local requests: ${foreign.join("; ")}`).toEqual([]);
  });
});
