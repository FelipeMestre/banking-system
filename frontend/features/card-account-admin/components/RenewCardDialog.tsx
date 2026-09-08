"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { renewCard } from "../api/renew-card";
import type { CardIssued } from "../types";
import { ReasonField } from "./ReasonField";

/** `POST /card-accounts/{id}/cards` — rotates card number + expiry; the old
 * card becomes `replaced`. 409 if the account isn't active. */
export function RenewCardDialog({
  cardAccountId,
  onClose,
  onSuccess,
}: {
  cardAccountId: string;
  onClose: () => void;
  onSuccess: (issued: CardIssued) => void;
}) {
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleAccept() {
    if (pending) return;
    setError(null);
    setPending(true);
    renewCard(cardAccountId, { reason: reason.trim().length > 0 ? reason.trim() : undefined })
      .then((issued) => onSuccess(issued))
      .catch((caught: unknown) => {
        setPending(false);
        setError(caught instanceof Error ? caught.message : "Could not renew the card.");
      });
  }

  return (
    <Dialog title="Renew card" onClose={onClose} onAccept={handleAccept} acceptLabel="Renew" acceptDisabled={pending}>
      <div className="flex flex-col gap-ds-3">
        <p className="m-0">
          This issues a new card number and expiry for this account. The current card becomes
          replaced and can no longer be used.
        </p>
        <ReasonField value={reason} onChange={setReason} id="renew-card-reason" />
        {error ? <ErrorMessage message={error} /> : null}
      </div>
    </Dialog>
  );
}
