import { ApiError } from "./api";
import { clearParentSession, getParentSession } from "./parent-session";
import type {
  DigestPreview,
  ParentSessionResponse,
  ParentSettings,
  PendingCampaignBrief,
  RepSummary,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

/**
 * Thin fetch wrapper for /parent/* routes, parallel to lib/api.ts's
 * apiFetch but authenticated with the parent session token from
 * lib/parent-session.ts instead of a Supabase JWT. A 401 here always
 * means "no/invalid/expired parent session" (never "wrong role"), so we
 * clear the stored session on 401 to force back to the login screen.
 */
export async function parentApiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const session = getParentSession();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (session) headers.set("Authorization", `Bearer ${session.session_token}`);

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch (err) {
    throw new ApiError(0, "Could not reach the Teenure server. Please try again in a moment.");
  }

  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const body = await res.json();
      detail = body.error?.message ?? body.detail ?? body;
    } catch {
      // no JSON body
    }
    if (res.status === 401) clearParentSession();
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const parentApi = {
  requestLink: (parent_email: string) =>
    parentApiFetch<{ status: string }>("/parent/auth/request-link", {
      method: "POST",
      body: JSON.stringify({ parent_email }),
    }),
  verify: (token: string) => parentApiFetch<ParentSessionResponse>(`/parent/auth/verify/${token}`),
  getDashboard: () => parentApiFetch<RepSummary>("/parent/dashboard"),
  getPendingCampaigns: () => parentApiFetch<PendingCampaignBrief[]>("/parent/campaigns/pending"),
  approveCampaign: (campaignId: string) =>
    parentApiFetch(`/parent/campaigns/${campaignId}/approve`, { method: "POST" }),
  blockCampaign: (campaignId: string) =>
    parentApiFetch(`/parent/campaigns/${campaignId}/block`, { method: "POST" }),
  getSettings: () => parentApiFetch<ParentSettings>("/parent/settings"),
  updateValuesFilters: (values_filters: string[]) =>
    parentApiFetch<ParentSettings>("/parent/settings/values-filters", {
      method: "PUT",
      body: JSON.stringify({ values_filters }),
    }),
  updateApprovalRequired: (campaign_approval_required: boolean) =>
    parentApiFetch<ParentSettings>("/parent/settings/approval-required", {
      method: "PUT",
      body: JSON.stringify({ campaign_approval_required }),
    }),
  updateDigestEnabled: (digest_enabled: boolean) =>
    parentApiFetch<ParentSettings>("/parent/settings/digest", {
      method: "PUT",
      body: JSON.stringify({ digest_enabled }),
    }),
  getDigestPreview: () => parentApiFetch<DigestPreview>("/parent/digest/preview"),
  suspendAccount: () => parentApiFetch<{ status: string }>("/parent/account/suspend", { method: "POST" }),
  unsuspendAccount: () => parentApiFetch<{ status: string }>("/parent/account/unsuspend", { method: "POST" }),
};
