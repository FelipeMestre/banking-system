"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { CardAccount } from "@/features/credit-cards/types";
import { updateCreditLimit } from "../api/update-credit-limit";
import { ReasonField } from "./ReasonField";

/** `PUT /card-accounts/{id}` — updates `credit_limit` only. */
export function UpdateCreditLimitDialog({
  cardAccount,
  onClose,
  onSuccess,
}: {
  cardAccount: CardAccount;
  onClose: () => void;
  onSuccess: (updated: CardAccount) => void;
}) {
  const [creditLimit, setCreditLimit] = useState(cardAccount.credit_limit);
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const creditLimitValue = Number(creditLimit);
  const isValid = creditLimit.trim().length > 0 && Number.isFinite(creditLimitValue) && creditLimitValue > 0;

  function handleAccept() {
    if (!isValid || pending) return;
    setError(null);
    setPending(true);
    updateCreditLimit(cardAccount.id, {
      credit_limit: creditLimit.trim(),
      reason: reason.trim().length > 0 ? reason.trim() : undefined,
    })
      .then((updated) => onSuccess(updated))
      .catch((caught: unknown) => {
        setPending(false);
        setError(caught instanceof Error ? caught.message : "Could not update the credit limit.");
      });
  }

  return (
    <Dialog
      title="Update credit limit"
      onClose={onClose}
      onAccept={handleAccept}
      acceptLabel="Update"
      acceptDisabled={!isValid || pending}
    >
      <div className="flex flex-col gap-ds-3">
        <div className="field">
          <Label htmlFor="update-limit-credit-limit">New credit limit</Label>
          <Input
            id="update-limit-credit-limit"
            value={creditLimit}
            onChange={(event) => setCreditLimit(event.target.value)}
            inputMode="decimal"
            autoFocus
          />
        </div>
        <ReasonField value={reason} onChange={setReason} id="update-limit-reason" />
        {error ? <ErrorMessage message={error} /> : null}
      </div>
    </Dialog>
  );
}
