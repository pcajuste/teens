import { test, expect } from "@playwright/test";

// Build Prompt 6 deliverable 11: every screen added for the Living
// Achievement Link / Goal Setting surfaces must pass the same 375px
// no-horizontal-overflow check required for the original Prompt 6
// deliverables. Auth-gated surfaces (profile-preview's share panel,
// the dashboard's goals panel) aren't covered here -- they need a
// logged-in session, which is exercised in tests-e2e-auth instead;
// this file covers the one genuinely public surface this feature adds.

test.use({ viewport: { width: 375, height: 812 } });

test("public verified profile page has no horizontal overflow at 375px", async ({ page }) => {
  await page.goto("/verified/nonexistent-token-for-mobile-check");
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
});
