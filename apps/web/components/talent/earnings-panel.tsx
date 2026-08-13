import type { Earnings } from "@/lib/types";

function money(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

// lifetime_paid_cents (talent_profiles.total_earnings_cents, cached) is
// the durable lifetime figure; paid_cents is a live sum over current
// campaign_reps rows and can differ transiently -- shown separately so
// the distinction isn't hidden from the talent.
// DS Section 6: only confirmed/paid amounts are gold (earned); pending
// is still text-1 -- nothing has been earned yet on that row. Lifetime
// paid is the single most important earned number on the dashboard, so
// it's larger and bolder than the three breakdown figures above it.
export function EarningsPanel({ earnings }: { earnings: Earnings }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      <div className="rounded-lg border border-border-muted p-2.5">
        <p className="text-xs text-text-3">Pending</p>
        <p className="text-base font-semibold">
          {money(earnings.pending_cents)}
        </p>
      </div>
      <div className="rounded-lg border border-gold-border bg-gold-dim p-2.5">
        <p className="text-xs text-text-3">Confirmed</p>
        <p className="text-base font-semibold text-gold">
          {money(earnings.confirmed_cents)}
        </p>
      </div>
      <div className="rounded-lg border border-gold-border bg-gold-dim p-2.5">
        <p className="text-xs text-text-3">Paid</p>
        <p className="text-base font-semibold text-gold">{money(earnings.paid_cents)}</p>
      </div>
      <div className="col-span-3 rounded-lg border border-gold-border bg-gold-dim p-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-gold">Lifetime paid</p>
        <p className="text-2xl font-extrabold text-gold">
          {money(earnings.lifetime_paid_cents)}
        </p>
      </div>

      {earnings.milestone_campaigns.length > 0 ? (
        <div className="col-span-3 flex flex-col gap-2">
          <p className="text-xs font-medium text-text-3">
            Milestone campaigns
          </p>
          {earnings.milestone_campaigns.map((mc) => {
            const remaining = mc.milestones.filter(
              (m) => m.status !== "confirmed" && m.status !== "paid",
            ).length;
            return (
              <div
                key={mc.campaign_id}
                className="rounded-lg border border-border p-2.5"
              >
                <p className="text-sm font-medium">{mc.campaign_title}</p>
                {/* Earned (confirmed/paid) vs. achievable (what remains through
                    the talent's own further effort) is always shown as two
                    numbers, never blended -- Build Prompt 8B's UX guidance:
                    never "guaranteed base + bonus" language, since nothing
                    here is contingent on anyone but the talent. */}
                <p className="text-xs text-text-2">
                  You have earned {money(mc.total_milestone_payout_cents)}
                  {mc.payout_per_talent_cents !== null
                    ? ` of ${money(mc.payout_per_talent_cents)} available`
                    : ""}
                  {" in this campaign. "}
                  {remaining} milestone{remaining === 1 ? "" : "s"} remaining.
                </p>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
