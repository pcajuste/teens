import type { Earnings } from "@/lib/types";

function money(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

// lifetime_paid_cents (rep_profiles.total_earnings_cents, cached) is
// the durable lifetime figure; paid_cents is a live sum over current
// campaign_reps rows and can differ transiently -- shown separately so
// the distinction isn't hidden from the rep.
export function EarningsPanel({ earnings }: { earnings: Earnings }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      <div className="rounded-lg border border-border p-2.5">
        <p className="text-xs text-muted-foreground">Pending</p>
        <p className="text-base font-semibold">{money(earnings.pending_cents)}</p>
      </div>
      <div className="rounded-lg border border-border p-2.5">
        <p className="text-xs text-muted-foreground">Confirmed</p>
        <p className="text-base font-semibold">{money(earnings.confirmed_cents)}</p>
      </div>
      <div className="rounded-lg border border-border p-2.5">
        <p className="text-xs text-muted-foreground">Paid</p>
        <p className="text-base font-semibold">{money(earnings.paid_cents)}</p>
      </div>
      <div className="col-span-3 rounded-lg border border-border bg-muted/40 p-2.5">
        <p className="text-xs text-muted-foreground">Lifetime paid</p>
        <p className="text-base font-semibold">{money(earnings.lifetime_paid_cents)}</p>
      </div>
    </div>
  );
}
