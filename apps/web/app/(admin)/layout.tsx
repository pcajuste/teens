"use client";

import { AuthProvider } from "@/lib/auth-context";
import { AuthGate } from "@/lib/auth-gate";

/** Admin route group layout. Reuses AuthGate (Build Prompt 13 auth
 * note: "its own gate should still reuse the AuthGate primitive...
 * since the loading/redirect mechanics are the same shape") but points
 * unauthenticated visitors at /admin-login, never the shared /login
 * page -- admin is a deliberately separate, heavily-protected surface,
 * not reachable via role-detection fallthrough. */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AuthGate role="admin" publicPaths={[]} signInPath="/admin-login">
        {children}
      </AuthGate>
    </AuthProvider>
  );
}
