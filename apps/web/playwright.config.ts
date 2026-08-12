import { defineConfig, devices } from "@playwright/test";

// apps/web's dev port per dev.sh (WEB_PORT default 3300) -- NOT the Next.js
// default of 3000. Keep this in sync with dev.sh / apps/web/package.json
// if either changes.
const PORT = process.env.WEB_PORT ?? "3300";
const BASE_URL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./tests-e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["html", { open: "never" }]],
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
  webServer: {
    // Production build + start for realistic smoke coverage. These pages
    // have no live Supabase/FastAPI backend in CI, but lib/supabase.ts
    // falls back to a placeholder client and these tests never submit
    // forms, so the pages render fine without real backend env vars.
    command: `pnpm build && PORT=${PORT} pnpm start`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
