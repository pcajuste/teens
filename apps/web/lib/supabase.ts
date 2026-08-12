import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

// Browser client used ONLY for session/login (signInWithPassword) after an
// account already exists. Account creation goes through FastAPI's
// POST /auth/signup, which creates both the Supabase auth.users row (via
// the Admin API) and the public.users row — do not call this client's own
// signUp() for account creation, per the build prompt's explicit
// instruction.
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
});
