import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ParticipationSection } from "@/app/(rep)/rep/campaigns/[id]/page";
import type { CampaignParticipation } from "@/lib/types";

function participation(overrides: Partial<CampaignParticipation> = {}): CampaignParticipation {
  return {
    campaign_id: "c1",
    status: "applied",
    ftc_disclosure_accepted: false,
    parent_approval_status: "not_required",
    parent_approval_deadline: null,
    submission_text: null,
    submission_file_urls: [],
    revision_note: null,
    ...overrides,
  } as CampaignParticipation;
}

describe("FTC disclosure gate", () => {
  it("disables Accept until the FTC checkbox is checked", async () => {
    const user = userEvent.setup();
    const onAccept = vi.fn();
    render(
      <ParticipationSection
        participation={participation()}
        ftcAccepted={false}
        setFtcAccepted={vi.fn()}
        onAccept={onAccept}
        onDecline={vi.fn()}
        onWithdrawn={vi.fn()}
        pending={false}
      />
    );

    const acceptButton = screen.getByRole("button", { name: "Accept" });
    expect(acceptButton).toBeDisabled();

    await user.click(acceptButton);
    expect(onAccept).not.toHaveBeenCalled();
  });

  it("enables Accept once the FTC checkbox is checked", () => {
    const onAccept = vi.fn();
    render(
      <ParticipationSection
        participation={participation()}
        ftcAccepted={true}
        setFtcAccepted={vi.fn()}
        onAccept={onAccept}
        onDecline={vi.fn()}
        onWithdrawn={vi.fn()}
        pending={false}
      />
    );

    expect(screen.getByRole("button", { name: "Accept" })).not.toBeDisabled();
  });
});

describe("parent-approval-pending state", () => {
  it("renders a waiting-on-parent message instead of the FTC/accept controls", () => {
    render(
      <ParticipationSection
        participation={participation({ parent_approval_status: "pending", parent_approval_deadline: "2026-08-20T00:00:00Z" })}
        ftcAccepted={false}
        setFtcAccepted={vi.fn()}
        onAccept={vi.fn()}
        onDecline={vi.fn()}
        onWithdrawn={vi.fn()}
        pending={false}
      />
    );

    expect(screen.getByText(/waiting on a parent's approval/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept" })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("renders a blocked message when the parent has blocked the campaign", () => {
    render(
      <ParticipationSection
        participation={participation({ parent_approval_status: "blocked" })}
        ftcAccepted={false}
        setFtcAccepted={vi.fn()}
        onAccept={vi.fn()}
        onDecline={vi.fn()}
        onWithdrawn={vi.fn()}
        pending={false}
      />
    );

    expect(screen.getByText(/your parent has blocked this campaign/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept" })).not.toBeInTheDocument();
  });
});
