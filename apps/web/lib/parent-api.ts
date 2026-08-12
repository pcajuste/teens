import { getParentSessionToken, clearParentSession } from "@/lib/parent-session";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export class ParentApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function parseError(res: Response): Promise<never> {
  let code = "unknown_error";
  let message = `Request failed with status ${res.status}`;
  try {
    const body = await res.json();
    if (body?.error?.code) {
      code = body.error.code;
      message = body.error.message ?? message;
    }
  } catch {
    // response body wasn't JSON -- fall back to the generic message above
  }
  if (res.status === 401) {
    // Session missing/expired/invalid on the backend -- clear the
    // stale local copy so the layout gate bounces to /parent on the
    // next render rather than looping on a dead token.
    clearParentSession();
  }
  throw new ParentApiError(code, message, res.status);
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown } = {}
): Promise<T> {
  const { method = "GET", body } = options;
  const token = getParentSessionToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    return parseError(res);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export const parentApi = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
};
