import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const getMock = vi.fn();
const postMock = vi.fn();

vi.mock("@/lib/parent-api", () => ({
  parentApi: {
    get: (...args: unknown[]) => getMock(...args),
    post: (...args: unknown[]) => postMock(...args),
  },
  ParentApiError: class ParentApiError extends Error {},
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/parent/campaigns",
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

import ParentCampaignsPage from "@/app/(parent)/parent/campaigns/page";

const PENDING_CAMPAIGN = {
  campaign_id: "camp-1",
  brand_name: "Acme Co",
  title: "Summer Launch",
  product_name: "Acme Shoes",
  campaign_goal: "Awareness",
  key_messaging: "Wear them everywhere",
  prohibited_content: null,
  deliverables_description: "One post",
  payout_per_rep_cents: 5000,
  start_date: "2026-09-01",
  end_date: "2026-09-30",
  requires_in_person_activation: false,
  parent_approval_deadline: null,
};

describe("parent portal approve/block actions", () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
  });

  it("calls the approve endpoint and refreshes the list after confirming", async () => {
    const user = userEvent.setup();
    getMock.mockResolvedValueOnce([PENDING_CAMPAIGN]).mockResolvedValueOnce([]);
    postMock.mockResolvedValueOnce({ campaign_id: "camp-1", parent_approval_status: "approved" });

    render(<ParentCampaignsPage />);

    await screen.findByText("Summer Launch");
    await user.click(screen.getByRole("button", { name: "Approve" }));

    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(postMock).toHaveBeenCalledWith("/parent/campaigns/camp-1/approve"));
    await waitFor(() => expect(getMock).toHaveBeenCalledTimes(2));
  });

  it("calls the block endpoint and refreshes the list after confirming", async () => {
    const user = userEvent.setup();
    getMock.mockResolvedValueOnce([PENDING_CAMPAIGN]).mockResolvedValueOnce([]);
    postMock.mockResolvedValueOnce({ campaign_id: "camp-1", parent_approval_status: "blocked" });

    render(<ParentCampaignsPage />);

    await screen.findByText("Summer Launch");
    await user.click(screen.getByRole("button", { name: "Block" }));

    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Block" }));

    await waitFor(() => expect(postMock).toHaveBeenCalledWith("/parent/campaigns/camp-1/block"));
    await waitFor(() => expect(getMock).toHaveBeenCalledTimes(2));
  });

  it("does not call the API until the confirm dialog is accepted", async () => {
    const user = userEvent.setup();
    getMock.mockResolvedValue([PENDING_CAMPAIGN]);

    render(<ParentCampaignsPage />);

    await screen.findByText("Summer Launch");
    await user.click(screen.getByRole("button", { name: "Approve" }));
    await screen.findByRole("dialog");

    expect(postMock).not.toHaveBeenCalled();
  });
});
