"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import type { MaskedCard } from "@/features/credit-cards/types";
import { updateCardStatus } from "../api/update-card-status";
import { ReasonField } from "./ReasonField";

const TITLE: Record<"active" | "blocked", string> = {
  active: "Unblock card",
  blocked: "Block card",
};

/** `POST /cards/{card_number}/status` — block/unblock the physical card,
 * independent of the account's own status. */
export function UpdateCardStatusDialog({
  card,
  targetStatus,
  onClose,
  onSuccess,
}: {
  card: MaskedCard;
  targetStatus: "active" | "blocked";
  onClose: () => void;
  onSuccess: (updated: MaskedCard) => void;
}) {
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleAccept() {
    if (pending) return;
    setError(null);
    setPending(true);
    updateCardStatus(card.card_number, {
      status: targetStatus,
      reason: reason.trim().length > 0 ? reason.trim() : undefined,
    })
      .then((updated) => onSuccess(updated))
      .catch((caught: unknown) => {
        setPending(false);
        setError(caught instanceof Error ? caught.message : "Could not update the card status.");
      });
  }

  return (
    <Dialog
      title={TITLE[targetStatus]}
      onClose={onClose}
      onAccept={handleAccept}
      acceptLabel={TITLE[targetStatus]}
      acceptDisabled={pending}
    >
      <div className="flex flex-col gap-ds-3">
        <ReasonField value={reason} onChange={setReason} id="card-status-reason" />
        {error ? <ErrorMessage message={error} /> : null}
      </div>
    </Dialog>
  );
}
