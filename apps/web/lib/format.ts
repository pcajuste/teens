export function formatCents(cents: number): string {
  return (cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return iso;
  }
}

/** Countdown string for a 48h invite expiry (CampaignSummary.invite_expires_at). */
export function countdown(iso: string | null): string | null {
  if (!iso) return null;
  const diffMs = new Date(iso).getTime() - Date.now();
  if (diffMs <= 0) return "Expired";
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
  return `${hours}h ${minutes}m left to respond`;
}

const STATUS_LABELS: Record<string, string> = {
  invited: "Invited",
  applied: "Applied",
  accepted: "Accepted",
  declined: "Declined",
  submitted: "Submitted",
  under_review: "Under review",
  revision_requested: "Revision requested",
  confirmed: "Confirmed",
  paid: "Paid",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}
