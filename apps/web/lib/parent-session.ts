"use client";

// Parent Portal session storage (Prompt 4A / Section 9A). Parents are not
// Supabase Auth users — there's no supabase.auth.getSession() to lean on
// here, so the signed parent session token (issued by
// GET /parent/auth/verify/:token) is kept in localStorage directly and
// attached manually by lib/parent-api.ts. This is intentionally a
// separate, parallel mechanism from lib/supabase.ts's rep/brand/recruiter
// session handling, not a shared one.

const STORAGE_KEY = "teenure_parent_session";

interface StoredParentSession {
  session_token: string;
  rep_id: string;
}

export function getParentSession(): StoredParentSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredParentSession;
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
