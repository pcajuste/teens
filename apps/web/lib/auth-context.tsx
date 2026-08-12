"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { supabase } from "./supabase";
import { api, ApiError } from "./api";
import type { MeResponse } from "./types";

interface AuthState {
  loading: boolean;
  session: boolean; // whether a Supabase session exists
  me: MeResponse | null;
  error: string | null;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  loading: true,
  session: false,
  me: null,
  error: null,
  refresh: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState(false);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await supabase.auth.getSession();
      const hasSession = !!data.session;
      setSession(hasSession);
      if (!hasSession) {
        setMe(null);
        return;
      }
      // GET /auth/me works for ANY authenticated user regardless of
      // account_status — used to detect "pending" before ever calling a
      // require-active-rep endpoint, so a pending rep never sees a raw 403.
      const meResponse = await api.me();
      setMe(meResponse);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Something went wrong loading your account.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const { data: sub } = supabase.auth.onAuthStateChange(() => {
      load();
    });
    return () => sub.subscription.unsubscribe();
  }, [load]);

  return (
    <AuthContext.Provider value={{ loading, session, me, error, refresh: load }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
