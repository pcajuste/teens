"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  confirmVariant?: "default" | "destructive";
  onCancel: () => void;
  /** Fires the real request. The dialog never assumes success locally --
   * the caller re-fetches/updates state from the response. */
  onConfirm: () => Promise<void>;
  children?: React.ReactNode;
  confirmDisabled?: boolean;
}

/** Generic confirm-before-firing dialog, generalized from
 * components/recruiter/credit-confirm-dialog.tsx so every "are you
 * sure" action across portals (not just credit spends) shares one
 * structure. */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  confirmVariant = "default",
  onCancel,
  onConfirm,
  children,
  confirmDisabled,
}: ConfirmDialogProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  async function handleConfirm() {
    setPending(true);
    setError(null);
    try {
      await onConfirm();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-md">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
        {children ? <div className="mt-4">{children}</div> : null}
        {error ? <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" onClick={onCancel} disabled={pending}>
            Cancel
          </Button>
          <Button type="button" variant={confirmVariant} onClick={handleConfirm} disabled={pending || confirmDisabled}>
            {pending ? "Working..." : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
