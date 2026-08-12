import { createClient } from "@supabase/supabase-js";

// Falls back to a syntactically-valid placeholder so `next build`'s
// static-generation pass (which imports this module even for
// "use client" pages) doesn't throw when real env vars aren't set --
// e.g. in this environment, with no live Supabase project configured.
// At runtime with real env vars set, these fallbacks are never used.
const url = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://placeholder.supabase.co";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "placeholder-anon-key";

export const supabase = createClient(url, anonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
});
