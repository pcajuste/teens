// Parents are not auth.users -- they never get a Supabase session, so
// they can't use lib/supabase.ts/lib/api.ts's session machinery. This
// is a lightweight, localStorage-backed stand-in for the 24-hour parent
// session token issued by GET /parent/auth/verify/:token.

const STORAGE_KEY = "teenure_parent_session";

interface StoredParentSession {
  session_token: string;
  expires_at: string;
}

export function getParentSession(): StoredParentSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredParentSession;
    if (!parsed.session_token) return null;
    if (new Date(parsed.expires_at).getTime() <= Date.now()) {
      clearParentSession();
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function setParentSession(session: StoredParentSession): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearParentSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}

export function getParentSessionToken(): string | null {
  return getParentSession()?.session_token ?? null;
}
