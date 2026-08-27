"use client";

import { useState } from "react";
import { Dialog } from "./Dialog";

interface Props {
  title: string;
  /** Plain confirmation copy — deliberately not a form. */
  message: React.ReactNode;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  confirmLabel?: string;
  busyLabel?: string;
}

/**
 * The yes/no counterpart to composing `Dialog` with a form: same chrome,
 * same submitting/error handling around a single async action, just a plain
 * message instead of an input. `DeleteLocationDialog` is the thin per-entity
 * wrapper around this — the same pattern LocationSaveDialog established for
 * create/edit.
 */
export function ConfirmDialog({
  title,
  message,
  onClose,
  onConfirm,
  confirmLabel = "Confirm",
  busyLabel = "Working…",
}: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAccept() {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      title={title}
      onClose={onClose}
      onAccept={handleAccept}
      acceptLabel={submitting ? busyLabel : confirmLabel}
      acceptDisabled={submitting}
    >
      {message}
      {error ? <p className="hint">{error}</p> : null}
    </Dialog>
  );
}
