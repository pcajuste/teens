import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { MeResponse } from "@/lib/types";

const useAuthMock = vi.fn();
const usePathnameMock = vi.fn(() => "/rep");
const useRouterMock = vi.fn(() => ({ replace: vi.fn() }));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => useAuthMock(),
}));
vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
  useRouter: () => useRouterMock(),
}));

import { AuthGate, CenteredMessage } from "@/lib/auth-gate";

function me(overrides: Partial<MeResponse> = {}): MeResponse {
  return { id: "u1", email: "rep@example.com", role: "rep", account_status: "pending", pending_reason: null, ...overrides };
}

describe("age-gate / pending-parental-consent screen", () => {
  it("renders the waiting-on-parent screen instead of the app for an under-16 pending account", () => {
    useAuthMock.mockReturnValue({
      session: { access_token: "t" },
      me: me({ pending_reason: "awaiting_parental_consent" }),
      loading: false,
    });

    render(
      <AuthGate
        role="rep"
        publicPaths={["/rep/signup"]}
        pendingState={(m) =>
          m.pending_reason === "awaiting_parental_consent" ? (
            <CenteredMessage title="Waiting on your parent">
              <p>Because you&apos;re under 16, a parent needs to approve your account.</p>
            </CenteredMessage>
          ) : null
        }
      >
        <div>Real dashboard content</div>
      </AuthGate>
    );

    expect(screen.getByText("Waiting on your parent")).toBeInTheDocument();
    expect(screen.queryByText("Real dashboard content")).not.toBeInTheDocument();
  });

  it("renders the real app once the account is active", () => {
    useAuthMock.mockReturnValue({
      session: { access_token: "t" },
      me: me({ account_status: "active", pending_reason: null }),
      loading: false,
    });

    render(
      <AuthGate
        role="rep"
        publicPaths={["/rep/signup"]}
        pendingState={(m) => (m.pending_reason === "awaiting_parental_consent" ? <div>Waiting</div> : null)}
      >
        <div>Real dashboard content</div>
      </AuthGate>
    );

    expect(screen.getByText("Real dashboard content")).toBeInTheDocument();
    expect(screen.queryByText("Waiting")).not.toBeInTheDocument();
  });
});
