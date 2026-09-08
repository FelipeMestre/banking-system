"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AccountSelect } from "@/components/shared/AccountSelect";
import { parseAmountToCents } from "@/lib/money";
import { getAccounts, type Account } from "@/features/accounts";
import { formatDecimalCurrency } from "../format-decimal";
import { getPaymentStatus } from "../api/get-payment-status";
import { requestPayment } from "../api/request-payment";
import { watchPaymentStatus } from "../api/watch-payment-status";
import type { CardPaymentAccepted, CardPaymentStatus } from "../types";

const ACCOUNTS_PAGE_SIZE = 50;

/** Quick-select presets for the current cycle, when known. All three are
 * genuinely backed by real data: `minimum`/`full` come straight off the
 * selected `Statement`, and `installmentPayoff` off `GET
 * /card-accounts/{id}/installment-payoff` (`credit-card-monthly-batch-
 * statements`) — none of them are guessed. Every preset only ever fills in
 * the same editable amount field; the customer still confirms what actually
 * gets submitted. */
export interface PayDialogPresets {
  minimum?: string;
  full?: string;
  installmentPayoff?: string;
}

interface Props {
  cardAccountId: string;
  onClose: () => void;
  /** Called once a payment has actually been accepted — the caller refreshes
   * the used-credit estimate (spec: "refreshing the used-credit approximation
   * afterward reflects the reduction"). */
  onPaid?: () => void;
  presets?: PayDialogPresets;
}

/**
 * Free-form amount, with optional quick-select presets for the minimum
 * payment, the full statement balance, and settling installment balances
 * early (`credit-card-monthly-batch-statements`) when the caller has that
 * data for the selected cycle. Live pending -> approved status mirrors
 * `SimulatePurchaseDialog`'s exact watcher pattern, pointed at the real
 * `payments/{request_id}/status` endpoint.
 */
export function PayDialog({ cardAccountId, onClose, onPaid, presets }: Props) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [sourceAccount, setSourceAccount] = useState("");
  const [amount, setAmount] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CardPaymentAccepted | null>(null);
  const [liveStatus, setLiveStatus] = useState<CardPaymentStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAccounts({ limit: ACCOUNTS_PAGE_SIZE, offset: 0 })
      .then((page) => {
        if (cancelled) return;
        setAccounts(page.items);
        setSourceAccount((current) => current || (page.items[0]?.account_number ?? ""));
      })
      .catch(() => {
        if (!cancelled) setAccounts([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const watchedRequestId =
    result && liveStatus?.status !== "approved" && liveStatus?.status !== "declined"
      ? result.request_id
      : null;

  const applyStatus = useCallback(
    (requestId: string, status: CardPaymentStatus) => {
      // The guard only ever needs `result` (closed over below), never the
      // previous `liveStatus` — so this can be a plain `setLiveStatus(status)`
      // rather than the updater-function form. Calling `onPaid?.()` (which
      // triggers state updates in the parent, `CreditCardsPageScreen`) from
      // inside a `setState` updater runs it during React's render phase,
      // which is exactly what "Cannot update a component while rendering a
      // different component" warns about — and can silently drop the
      // parent's refresh, which is why the used-credit bar stayed stale.
      if (result?.request_id !== requestId) return;
      setLiveStatus(status);
      if (status.status === "approved") onPaid?.();
    },
    [result, onPaid],
  );

  useEffect(() => {
    if (watchedRequestId === null) return;

    return watchPaymentStatus(watchedRequestId, {
      onStatus: (status) => applyStatus(watchedRequestId, status),
      onUnavailable: () => {
        void getPaymentStatus(watchedRequestId)
          .then((status) => applyStatus(watchedRequestId, status))
          .catch(() => {
            // Best-effort live view only — the customer can still close the dialog.
          });
      },
    });
  }, [watchedRequestId, applyStatus]);

  const parsedCents = parseAmountToCents(amount);
  const canSubmit = !pending && !result && parsedCents !== null && sourceAccount !== "";

  function handleSubmit() {
    if (parsedCents === null || sourceAccount === "") return;
    setError(null);
    setPending(true);
    setLiveStatus(null);
    requestPayment(cardAccountId, { amount: parsedCents, source_account: sourceAccount })
      .then((accepted) => {
        setPending(false);
        setResult(accepted);
      })
      .catch((caught: unknown) => {
        setPending(false);
        setError(caught instanceof Error ? caught.message : "Could not submit the payment.");
      });
  }

  function handleAccept() {
    if (result) {
      onClose();
      return;
    }
    handleSubmit();
  }

  const acceptLabel = result ? "Close" : pending ? "Submitting…" : "Submit payment";
  const acceptDisabled = result ? false : !canSubmit;

  return (
    <Dialog
      title="Pay your card"
      onClose={onClose}
      onAccept={handleAccept}
      acceptLabel={acceptLabel}
      cancelLabel="Cancel"
      acceptDisabled={acceptDisabled}
      hideCancel={result !== null}
    >
      {result ? (
        <div className="flex flex-col gap-ds-3">
          <p className="m-0">Payment request accepted.</p>
          <div className="flex flex-col gap-ds-1 border-2 border-divider p-ds-3 text-sm">
            <span>
              Status: <strong>{liveStatus?.status ?? "pending"}</strong>
            </span>
            <span className="font-mono text-xs break-all">Request ID: {result.request_id}</span>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-ds-3">
          <AccountSelect
            id="pay-from-account"
            label="Pay from"
            value={sourceAccount}
            onChange={setSourceAccount}
            accounts={accounts}
          />
          {presets ? (
            <div className="flex flex-wrap gap-ds-2">
              {presets.minimum ? (
                <Button type="button" variant="secondary" size="sm" onClick={() => setAmount(presets.minimum!)}>
                  Pay minimum ({formatDecimalCurrency(presets.minimum)})
                </Button>
              ) : null}
              {presets.full ? (
                <Button type="button" variant="secondary" size="sm" onClick={() => setAmount(presets.full!)}>
                  Pay in full ({formatDecimalCurrency(presets.full)})
                </Button>
              ) : null}
              {presets.installmentPayoff && Number(presets.installmentPayoff) > 0 ? (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setAmount(presets.installmentPayoff!)}
                >
                  Settle installments early ({formatDecimalCurrency(presets.installmentPayoff)})
                </Button>
              ) : null}
            </div>
          ) : null}
          <div className="field">
            <Label htmlFor="payment-amount">Amount</Label>
            <Input
              id="payment-amount"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              placeholder="100.00"
              inputMode="decimal"
              autoComplete="off"
            />
          </div>
          {error ? <ErrorMessage message={error} /> : null}
        </div>
      )}
    </Dialog>
  );
}
