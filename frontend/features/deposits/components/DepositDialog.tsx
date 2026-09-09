"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Account } from "@/features/accounts/types";
import { currencySymbol, formatAccountNumber, parseAmountToCents } from "@/lib/money";
import { createDeposit } from "../api/create-deposit";
import type { DepositResponse } from "../types";
import { AccountPicker } from "./AccountPicker";

const CURRENCIES = ["USD", "EUR", "GBP"] as const;
const REASON_MAX_LENGTH = 300;

interface Props {
  onClose: () => void;
  onSuccess: (response: DepositResponse, account: Account) => void;
}

/**
 * Admin cash-deposit flow: pick an account (and see the customer it belongs
 * to), fill amount/currency/reason, submit to `POST /admin/deposits`. One
 * `Dialog`, no separate result step inside it — the successful response
 * bubbles up via `onSuccess` and the caller (AccountsPanel) shows the
 * outcome, matching how CreateAccountDialog hands the created account back
 * rather than rendering its own success screen.
 */
export function DepositDialog({ onClose, onSuccess }: Props) {
  const [account, setAccount] = useState<Account | null>(null);
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState<string>("USD");
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cents = parseAmountToCents(amount);
  const acceptDisabled = pending || account === null || cents === null;

  function handleAccept() {
    if (account === null || cents === null) return;
    setError(null);
    setPending(true);
    createDeposit({
      account_number: account.account_number,
      amount: cents,
      currency,
      reason: reason.trim().length > 0 ? reason.trim() : undefined,
    })
      .then((response) => {
        onSuccess(response, account);
      })
      .catch((caught: unknown) => {
        setPending(false);
        setError(caught instanceof Error ? caught.message : "Could not complete the deposit.");
      });
  }

  return (
    <Dialog
      title="Deposit"
      onClose={onClose}
      onAccept={handleAccept}
      acceptLabel="Deposit"
      acceptDisabled={acceptDisabled}
    >
      <div className="flex flex-col gap-ds-3">
        <AccountPicker selected={account} onSelect={setAccount} />

        {account ? (
          <p className="m-0 text-xs text-neutral-600">
            Depositing into {formatAccountNumber(account.account_number)}.
          </p>
        ) : null}

        <div className="field">
          <Label htmlFor="deposit-amount">Amount</Label>
          <Input
            id="deposit-amount"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            inputMode="decimal"
            autoComplete="off"
            placeholder="0.00"
            disabled={pending}
          />
        </div>

        <div className="field">
          <Label htmlFor="deposit-currency">Currency</Label>
          <Select value={currency} onValueChange={setCurrency}>
            <SelectTrigger id="deposit-currency" className="w-full" disabled={pending}>
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
          <Label htmlFor="deposit-reason">Reason (optional)</Label>
          <Input
            id="deposit-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value.slice(0, REASON_MAX_LENGTH))}
            autoComplete="off"
            disabled={pending}
          />
        </div>

        {error ? <ErrorMessage message={error} /> : null}
      </div>
    </Dialog>
  );
}
