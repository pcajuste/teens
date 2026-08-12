"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";

// One-tap, no confirmation dialog by design (Section 9: frictionless
// withdrawal). Do not add a confirm step here.
export function WithdrawButton({
  campaignId,
  onWithdrawn,
  className,
}: {
  campaignId: string;
  onWithdrawn: () => void;
  className?: string;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleWithdraw() {
    setPending(true);
    setError(null);
    try {
      await api.post(`/campaigns/${campaignId}/withdraw`);
      onWithdrawn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not withdraw. Try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className={className}>
      <Button
        type="button"
        variant="destructive"
        size="sm"
        className="h-9 w-full"
        disabled={pending}
        onClick={handleWithdraw}
      >
        {pending ? "Withdrawing..." : "Withdraw"}
      </Button>
      {error ? <p className="mt-1 text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
