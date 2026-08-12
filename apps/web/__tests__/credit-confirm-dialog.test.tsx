import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreditConfirmDialog } from "@/components/recruiter/credit-confirm-dialog";

describe("CreditConfirmDialog", () => {
  it("does not fire the credit-spending action until the user confirms", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn().mockResolvedValue(undefined);

    render(
      <CreditConfirmDialog
        open={true}
        title="View full profile"
        description="This costs 1 credit."
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />
    );

    // Rendering the dialog alone must never spend a credit.
    expect(onConfirm).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /use 1 credit/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("cancel closes without ever calling onConfirm", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      <CreditConfirmDialog
        open={true}
        title="Contact this rep"
        description="This costs 1 credit."
        onCancel={onCancel}
        onConfirm={onConfirm}
      />
    );

    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("renders nothing when closed", () => {
    render(
      <CreditConfirmDialog open={false} title="x" description="y" onCancel={vi.fn()} onConfirm={vi.fn()} />
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
