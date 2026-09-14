"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import type { CardAccount } from "@/features/credit-cards/types";
import { updateCardAccountStatus } from "../api/update-card-account-status";
import { ReasonField } from "./ReasonField";

const TITLE: Record<CardAccount["status"], string> = {
  active: "Unblock card account",
  blocked: "Block card account",
  closed: "Close card account",
};

/**
 * `POST /card-accounts/{id}/status` — block/unblock/close the account.
 * Closing is balance-guarded server-side: a 409 `CardAccountNotCloseableError`
 * carries a human-readable message (via `error.message`, already surfaced by
 * `describeFailure`) that this dialog shows verbatim rather than a generic
 * "failed" — closed is also terminal, so the copy warns it can't be undone.
 */
export function UpdateCardAccountStatusDialog({
  cardAccount,
  targetStatus,
  onClose,
  onSuccess,
}: {
  cardAccount: CardAccount;
  targetStatus: CardAccount["status"];
  onClose: () => void;
  onSuccess: (updated: CardAccount) => void;
}) {
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleAccept() {
    if (pending) return;
    setError(null);
    setPending(true);
    updateCardAccountStatus(cardAccount.id, {
      status: targetStatus,
      reason: reason.trim().length > 0 ? reason.trim() : undefined,
    })
      .then((updated) => onSuccess(updated))
      .catch((caught: unknown) => {
        setPending(false);
        setError(caught instanceof Error ? caught.message : "Could not update the account status.");
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
        {targetStatus === "closed" ? (
          <p className="m-0">
            Closing is permanent — a closed account cannot be reopened. Closing fails if the
            account still carries a balance.
          </p>
        ) : null}
        <ReasonField value={reason} onChange={setReason} id="account-status-reason" />
        {error ? <ErrorMessage message={error} /> : null}
      </div>
    </Dialog>
  );
}
