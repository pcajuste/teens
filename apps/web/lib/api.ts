import { supabase } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export class ApiError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseError(res: Response): Promise<never> {
  let code = "unknown_error";
  let message = `Request failed with status ${res.status}`;
  try {
    const body = await res.json();
    // Every 4xx/5xx from apps/api is shaped {"error": {"code", "message"}}
    // -- see apps/api/app/core/errors.py's register_exception_handlers.
    if (body?.error?.code) {
      code = body.error.code;
      message = body.error.message ?? message;
    }
  } catch {
    // response body wasn't JSON -- fall back to the generic message above
  }
  throw new ApiError(code, message);
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; isFormData?: boolean } = {}
): Promise<T> {
  const { method = "GET", body, isFormData = false } = options;
  const headers: Record<string, string> = await authHeader();
  if (!isFormData) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: isFormData ? (body as FormData) : body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    return parseError(res);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, { method: "POST", body: form, isFormData: true }),
};
