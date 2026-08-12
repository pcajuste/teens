"use client";

import { AuthProvider } from "@/lib/auth-context";
import { RepGate } from "@/app/(rep)/rep-gate";

export default function RepLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <RepGate>{children}</RepGate>
    </AuthProvider>
  );
}
