"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { issueCardAccount } from "../api/issue-card-account";
import type { IssueCardAccountResponse } from "../types";
import { AccountPicker } from "./AccountPicker";
import { ReasonField } from "./ReasonField";

/**
 * `POST /card-accounts` — creates the card account and its first (unmasked)
 * card atomically. `credit_limit` is validated client-side as a positive
 * decimal-as-string before Issue is enabled; the backend remains the source
 * of truth (a 422 still surfaces inline on a rejected value).
 *
 * `customerId` is a required prop, not internal state: the customer is
 * already selected one screen up (`CardAccountAdminPanel`/`CardAccountsList`)
 * before this dialog opens, so it no longer re-picks a customer — it only
 * picks which of THAT customer's accounts pays for the card, via
 * `AccountPicker` instead of a free-text UUID field.
 */
export function IssueCardAccountDialog({
  customerId,
  onClose,
  onSuccess,
}: {
  customerId: string;
  onClose: () => void;
  onSuccess: (issued: IssueCardAccountResponse) => void;
}) {
  const [payingAccountId, setPayingAccountId] = useState("");
  const [creditLimit, setCreditLimit] = useState("");
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const creditLimitValue = Number(creditLimit);
  const isCreditLimitValid = creditLimit.trim().length > 0 && Number.isFinite(creditLimitValue) && creditLimitValue > 0;
  const canSubmit = !pending && payingAccountId.trim().length > 0 && isCreditLimitValid;

  function handleAccept() {
    if (!canSubmit) return;
    setError(null);
    setPending(true);
    issueCardAccount({
      customer_id: customerId,
      paying_account_id: payingAccountId.trim(),
      credit_limit: creditLimit.trim(),
      reason: reason.trim().length > 0 ? reason.trim() : undefined,
    })
      .then((issued) => onSuccess(issued))
      .catch((caught: unknown) => {
        setPending(false);
        setError(caught instanceof Error ? caught.message : "Could not issue the card account.");
      });
  }

  return (
    <Dialog
      title="Issue card account"
      onClose={onClose}
      onAccept={handleAccept}
      acceptLabel="Issue"
      acceptDisabled={!canSubmit}
    >
      <div className="flex flex-col gap-ds-3">
        <AccountPicker
          customerId={customerId}
          value={payingAccountId.trim().length > 0 ? payingAccountId : null}
          onChange={setPayingAccountId}
        />
        <div className="field">
          <Label htmlFor="issue-credit-limit">Credit limit</Label>
          <Input
            id="issue-credit-limit"
            value={creditLimit}
            onChange={(event) => setCreditLimit(event.target.value)}
            placeholder="e.g. 5000.00"
            inputMode="decimal"
          />
        </div>
        <ReasonField value={reason} onChange={setReason} id="issue-reason" />
        {error ? <ErrorMessage message={error} /> : null}
      </div>
    </Dialog>
  );
}
