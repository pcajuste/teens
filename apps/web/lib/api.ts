import { supabase } from "./supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function getAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

/**
 * Thin fetch wrapper against the FastAPI backend. Attaches the Supabase
 * session JWT as `Authorization: Bearer <token>` when present. Never
 * throws on network failure silently — callers are expected to catch and
 * render a graceful error/loading state (the backend's Supabase Storage
 * calls, in particular, have no real credentials in local dev and may
 * 502; UI must degrade, not crash).
 */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getAccessToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

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
      detail = body.detail ?? body;
    } catch {
      // no JSON body
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  me: () => apiFetch<import("./types").MeResponse>("/auth/me"),
  getRepProfile: () => apiFetch<import("./types").RepProfile>("/reps/me"),
  updateRepProfile: (body: import("./types").RepProfileUpdate) =>
    apiFetch<import("./types").RepProfile>("/reps/me", { method: "PUT", body: JSON.stringify(body) }),
  getProfilePreview: () => apiFetch<import("./types").ProfilePreview>("/reps/me/profile-preview"),
  getAvailableCampaigns: () => apiFetch<import("./types").CampaignSummary[]>("/reps/campaigns/available"),
  getActiveCampaigns: () => apiFetch<import("./types").CampaignSummary[]>("/reps/campaigns/active"),
  getCampaignHistory: () => apiFetch<import("./types").CampaignSummary[]>("/reps/campaigns/history"),
  getEarnings: () => apiFetch<import("./types").EarningsBreakdown>("/reps/earnings"),
  applyToCampaign: (id: string) => apiFetch(`/campaigns/${id}/apply`, { method: "POST" }),
  acceptCampaign: (id: string, body: import("./types").AcceptRequest) =>
    apiFetch(`/campaigns/${id}/accept`, { method: "POST", body: JSON.stringify(body) }),
  declineCampaign: (id: string) => apiFetch(`/campaigns/${id}/decline`, { method: "POST" }),
  withdrawCampaign: (id: string) => apiFetch(`/campaigns/${id}/withdraw`, { method: "POST" }),
  submitCampaign: (id: string, body: import("./types").SubmitRequest) =>
    apiFetch(`/campaigns/${id}/submit`, { method: "POST", body: JSON.stringify(body) }),
  requestUploadUrl: (
    id: string,
    body: { file_name: string; content_type: string; file_size_bytes: number },
  ) => apiFetch<{ upload_url: string; file_url: string }>(`/campaigns/${id}/upload-url`, {
    method: "POST",
    body: JSON.stringify(body),
  }),
};
