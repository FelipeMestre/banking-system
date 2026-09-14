"use client";

import { useState } from "react";
import { AccountPicker } from "@/components/shared/AccountPicker";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Account } from "@/features/accounts/types";
import { currencySymbol, formatAccountNumber, parseAmountToCents } from "@/lib/money";
import { createWithdrawal } from "../api/create-withdrawal";
import type { WithdrawalResponse } from "../types";

const CURRENCIES = ["USD", "EUR", "GBP"] as const;
const REASON_MAX_LENGTH = 300;

const DECLINE_REASON_LABEL: Record<string, string> = {
  insufficient_funds: "Insufficient funds in this account.",
  invalid_amount: "That amount isn't valid.",
};

function describeDecline(reason: string | undefined): string {
  if (!reason) return "The withdrawal was declined.";
  return DECLINE_REASON_LABEL[reason] ?? reason;
}

interface Props {
  onClose: () => void;
  onSuccess: (response: WithdrawalResponse, account: Account) => void;
}

/**
 * Admin cash-withdrawal flow: pick an account (and see the customer it
 * belongs to), fill amount/currency/reason, submit to
 * `POST /admin/withdrawals`. Mirrors `DepositDialog` closely, with one real
 * behavioral difference: a withdrawal can be declined (e.g. insufficient
 * funds) as a normal, resolved outcome (`approved: false`, still HTTP 200).
 * A decline is surfaced inline — same shape as `SimulatePurchaseDialog`'s
 * decline handling — and leaves the dialog open with Accept re-enabled so
 * the admin can correct the amount and retry; only an approved outcome
 * bubbles up via `onSuccess`.
 */
export function WithdrawalDialog({ onClose, onSuccess }: Props) {
  const [account, setAccount] = useState<Account | null>(null);
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState<string>("USD");
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [declineMessage, setDeclineMessage] = useState<string | null>(null);

  const cents = parseAmountToCents(amount);
  const acceptDisabled = pending || account === null || cents === null;

  function handleAccept() {
    if (account === null || cents === null) return;
    setError(null);
    setDeclineMessage(null);
    setPending(true);
    createWithdrawal({
      account_number: account.account_number,
      amount: cents,
      currency,
      reason: reason.trim().length > 0 ? reason.trim() : undefined,
    })
      .then((response) => {
        if (response.approved) {
          onSuccess(response, account);
          return;
        }
        setPending(false);
        setDeclineMessage(describeDecline(response.reason));
      })
      .catch((caught: unknown) => {
        setPending(false);
        setError(caught instanceof Error ? caught.message : "Could not complete the withdrawal.");
      });
  }

  return (
    <Dialog
      title="Withdraw"
      onClose={onClose}
      onAccept={handleAccept}
      acceptLabel="Withdraw"
      acceptDisabled={acceptDisabled}
    >
      <div className="flex flex-col gap-ds-3">
        <AccountPicker selected={account} onSelect={setAccount} />

        {account ? (
          <p className="m-0 text-xs text-neutral-600">
            Withdrawing from {formatAccountNumber(account.account_number)}.
          </p>
        ) : null}

        <div className="field">
          <Label htmlFor="withdrawal-amount">Amount</Label>
          <Input
            id="withdrawal-amount"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            inputMode="decimal"
            autoComplete="off"
            placeholder="0.00"
            disabled={pending}
          />
        </div>

        <div className="field">
          <Label htmlFor="withdrawal-currency">Currency</Label>
          <Select value={currency} onValueChange={setCurrency}>
            <SelectTrigger id="withdrawal-currency" className="w-full" disabled={pending}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CURRENCIES.map((code) => (
                <SelectItem key={code} value={code}>
                  {currencySymbol(code)} {code}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="field">
          <Label htmlFor="withdrawal-reason">Reason (optional)</Label>
          <Input
            id="withdrawal-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value.slice(0, REASON_MAX_LENGTH))}
            autoComplete="off"
            disabled={pending}
          />
        </div>

        {declineMessage ? <ErrorMessage message={declineMessage} /> : null}
        {error ? <ErrorMessage message={error} /> : null}
      </div>
    </Dialog>
  );
}
