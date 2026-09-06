"use client";

import { useCallback, useEffect, useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { parseAmountToCents } from "@/lib/money";
import { getPaymentStatus } from "../api/get-payment-status";
import { requestPayment } from "../api/request-payment";
import { watchPaymentStatus } from "../api/watch-payment-status";
import type { CardPaymentAccepted, CardPaymentStatus } from "../types";

interface Props {
  cardAccountId: string;
  onClose: () => void;
  /** Called once a payment has actually been accepted — the caller refreshes
   * the used-credit estimate (spec: "refreshing the used-credit approximation
   * afterward reflects the reduction"). */
  onPaid?: () => void;
}

/**
 * Free-form amount only — no minimum-payment, full-payoff, or
 * installment-payoff presets, since no backing data exists for them (spec:
 * "Real Payment Flow"). Live pending -> approved status mirrors
 * `SimulatePurchaseDialog`'s exact watcher pattern, pointed at the real
 * `payments/{request_id}/status` endpoint.
 */
export function PayDialog({ cardAccountId, onClose, onPaid }: Props) {
  const [amount, setAmount] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CardPaymentAccepted | null>(null);
  const [liveStatus, setLiveStatus] = useState<CardPaymentStatus | null>(null);

  const watchedRequestId =
    result && liveStatus?.status !== "approved" && liveStatus?.status !== "declined"
      ? result.request_id
      : null;

  const applyStatus = useCallback(
    (requestId: string, status: CardPaymentStatus) => {
      setLiveStatus((current) => {
        if (result?.request_id !== requestId) return current;
        if (status.status === "approved") onPaid?.();
        return status;
      });
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
  const canSubmit = !pending && !result && parsedCents !== null;

  function handleSubmit() {
    if (parsedCents === null) return;
    setError(null);
    setPending(true);
    setLiveStatus(null);
    requestPayment(cardAccountId, { amount: parsedCents })
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
      cancelLabel={result ? "Close" : "Cancel"}
      acceptDisabled={acceptDisabled}
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
