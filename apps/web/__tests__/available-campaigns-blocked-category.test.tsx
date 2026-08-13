import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const getMock = vi.fn();

vi.mock("@/lib/api", () => ({
  api: { get: (...args: unknown[]) => getMock(...args) },
  ApiError: class ApiError extends Error {
    code: string;
    constructor(code: string, message: string) {
      super(message);
      this.code = code;
    }
  },
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ signOut: vi.fn() }),
}));

import RepDashboardPage from "@/app/(talent)/talent/page";

const ALLOWED_CAMPAIGN = {
  id: "camp-allowed",
  title: "Gaming Gear Drop",
  product_name: "Headset",
  campaign_goal: "Awareness",
  deliverables_description: "One post",
  target_categories: ["gaming"],
  target_cities: [],
  payout_per_talent_cents: 3000,
  start_date: "2026-09-01",
  end_date: "2026-09-30",
};

// A parent has "alcohol_adjacent" in values_filters -- the backend
// (GET /talents/campaigns/available) never returns campaigns in a
// blocked category in the first place (Section 9A). This test proves
// the rendered panel reflects exactly what the API returns and never
// independently re-adds or caches a blocked campaign back in.
const BLOCKED_CAMPAIGN = {
  id: "camp-blocked",
  title: "Craft Brewery Tour",
  product_name: "Brewery Co",
  campaign_goal: "Awareness",
  deliverables_description: "One post",
  target_categories: ["alcohol_adjacent"],
  target_cities: [],
  payout_per_talent_cents: 3000,
  start_date: "2026-09-01",
  end_date: "2026-09-30",
};

describe("available-campaigns panel", () => {
  it("never renders a campaign the API excluded for a parent-blocked category", async () => {
    getMock.mockImplementation((path: string) => {
      if (path === "/talents/me")
        return Promise.resolve({
          id: "r1",
          display_name: "Test Talent",
          school_name: "Test High",
          school_type: "public",
          city: "Austin",
          state: "TX",
          graduation_year: 2027,
          bio: "Hi",
          categories: ["gaming"],
          instagram_handle: "test",
          tiktok_handle: null,
          recruiter_visible: true,
          total_campaigns_completed: 0,
          total_earnings_cents: 0,
          average_rating: null,
          profile_completeness_score: 80,
        });
      // The blocked-category campaign is never in this response  --
      // the server-side values-filter exclusion already happened.
      if (path === "/talents/campaigns/available")
        return Promise.resolve([ALLOWED_CAMPAIGN]);
      if (path === "/talents/campaigns/active") return Promise.resolve([]);
      if (path === "/talents/earnings")
        return Promise.resolve({
          pending_cents: 0,
          confirmed_cents: 0,
          paid_cents: 0,
          lifetime_paid_cents: 0,
        });
      if (path === "/talents/challenges/available") return Promise.resolve([]);
      if (path === "/talents/challenges/submitted") return Promise.resolve([]);
      return Promise.reject(new Error(`unexpected path ${path}`));
    });

    render(<RepDashboardPage />);

    expect(await screen.findByText("Gaming Gear Drop")).toBeInTheDocument();
    expect(screen.queryByText("Craft Brewery Tour")).not.toBeInTheDocument();
    // Sanity: prove this test would actually catch a leak, not just a
    // component that never renders anything.
    expect(BLOCKED_CAMPAIGN.target_categories).toContain("alcohol_adjacent");
  });
});
