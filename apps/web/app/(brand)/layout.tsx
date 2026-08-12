"use client";

import { AuthProvider } from "@/lib/auth-context";
import { BrandGate } from "@/app/(brand)/brand-gate";

export default function BrandLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <BrandGate>{children}</BrandGate>
    </AuthProvider>
  );
}
