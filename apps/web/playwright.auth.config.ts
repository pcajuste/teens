import { defineConfig, devices } from "@playwright/test";

// Authenticated E2E suite: exercises real signup/login against a real
// FastAPI backend + local Supabase Auth (GoTrue), unlike playwright.config.ts's
// demo-portal suite which has zero backend dependency. Requires, running
// BEFORE this config is invoked:
//   1. `supabase start`                          (local Postgres + GoTrue)
//   2. apps/api's uvicorn on API_PORT (see apps/api/.env.local)
// See README.md's "Local database + auth" section, and
// .github/workflows/ci.yml's web-e2e-auth job for the CI equivalent.
const PORT = process.env.WEB_PORT ?? "3300";
const BASE_URL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./tests-e2e-auth",
  fullyParallel: false, // each test creates a real, uniquely-emailed auth.users row -- keep runs simple and serial
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["html", { open: "never", outputFolder: "playwright-report-auth" }]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // This still starts apps/web itself, same as playwright.config.ts, but
  // unlike that config it does NOT start apps/api or Supabase -- both
  // must already be running (dev.sh + `supabase start` locally, a
  // dedicated CI job in ci.yml), since Playwright has no lifecycle
  // hook for a non-Node backend process.
  webServer: {
    command: `pnpm build && PORT=${PORT} pnpm start`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
