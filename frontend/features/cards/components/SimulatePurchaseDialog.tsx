"use client";

import { useCallback, useEffect, useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingScreen } from "@/components/ui/loading-screen";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getCards } from "../api/get-cards";
import { getPurchaseStatus } from "../api/get-purchase-status";
import { requestPurchase } from "../api/request-purchase";
import { watchPurchaseStatus } from "../api/watch-purchase-status";
import { parsePurchaseAmount } from "../parse-purchase-amount";
import { CardSelect } from "./CardSelect";
import type { CardListItem, PurchaseAccepted, PurchaseStatus } from "../types";

interface Props {
  onClose: () => void;
}

// A small, useful spread for testing the gateway's currency conversion —
// not an exhaustive currency list, just USD plus a couple of foreign ones.
const CURRENCIES = ["USD", "EUR", "GBP"] as const;

// Matches `PurchaseRequestDTO.installments` (`Field(default=1, ge=1, le=24)`).
const MIN_INSTALLMENTS = 1;
const MAX_INSTALLMENTS = 24;

type CardsState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; cards: CardListItem[] };

/**
 * Admin-only testing tool: simulates a credit card purchase end to end
 * through the real `POST /cards/{card_number}/purchases` (Credit Cards
 * Phase 2). Sends only what a real client would naturally supply — amount,
 * currency, description, installments — the gateway resolves currency
 * conversion itself, so nothing here computes or displays an exchange rate.
 */
export function SimulatePurchaseDialog({ onClose }: Props) {
  const [cardsState, setCardsState] = useState<CardsState>({ kind: "loading" });
  const [cardId, setCardId] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState<string>("USD");
  const [description, setDescription] = useState("");
  const [installments, setInstallments] = useState("1");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PurchaseAccepted | null>(null);
  const [liveStatus, setLiveStatus] = useState<PurchaseStatus | null>(null);

  // Only a submitted, not-yet-resolved purchase is worth watching, and a
  // plain string keeps the effect's dependencies stable across re-renders.
  const watchedRequestId =
    result && liveStatus?.status !== "approved" && liveStatus?.status !== "declined"
      ? result.request_id
      : null;

  const applyStatus = useCallback(
    (requestId: string, status: PurchaseStatus) => {
      setLiveStatus((current) => {
        // A verdict for an abandoned purchase must not overwrite the current one.
        if (result?.request_id !== requestId) return current;
        return status;
      });
    },
    [result],
  );

  useEffect(() => {
    if (watchedRequestId === null) return;

    return watchPurchaseStatus(watchedRequestId, {
      onStatus: (status) => applyStatus(watchedRequestId, status),
      onUnavailable: () => {
        // The socket never delivered anything. Fall back to the pull
        // endpoint the gateway offers for exactly this case.
        void getPurchaseStatus(watchedRequestId)
          .then((status) => applyStatus(watchedRequestId, status))
          .catch(() => {
            // Leave the UI in its pending state — the admin can still close
            // the dialog, this is only a best-effort live view.
          });
      },
    });
  }, [watchedRequestId, applyStatus]);

  useEffect(() => {
    let cancelled = false;
    getCards({ limit: 100, offset: 0 })
      .then((page) => {
        if (!cancelled) setCardsState({ kind: "ready", cards: page.items });
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setCardsState({
            kind: "error",
            message: caught instanceof Error ? caught.message : "Could not load cards.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const cards = cardsState.kind === "ready" ? cardsState.cards : [];
  const selectedCard = cards.find((card) => card.id === cardId) ?? null;
  const parsedAmount = parsePurchaseAmount(amount);
  const parsedInstallments = Number(installments);
  const installmentsValid =
    installments.trim().length > 0 &&
    Number.isInteger(parsedInstallments) &&
    parsedInstallments >= MIN_INSTALLMENTS &&
    parsedInstallments <= MAX_INSTALLMENTS;

  const canSubmit = !pending && !result && selectedCard !== null && parsedAmount !== null && installmentsValid;

  function handleSubmit() {
    if (!selectedCard || !parsedAmount || !installmentsValid) return;
    setError(null);
    setPending(true);
    setLiveStatus(null);
    requestPurchase(selectedCard.card_number, {
      card_id: selectedCard.id,
      amount: parsedAmount,
      currency,
      description: description.trim() ? description.trim() : undefined,
      installments: parsedInstallments,
    })
      .then((accepted) => {
        setPending(false);
        setResult(accepted);
      })
      .catch((caught: unknown) => {
        setPending(false);
        setError(caught instanceof Error ? caught.message : "Could not submit the purchase.");
      });
  }

  function handleAccept() {
    if (result) {
      onClose();
      return;
    }
    handleSubmit();
  }

  const acceptLabel = result ? "Close" : pending ? "Submitting…" : "Submit purchase";
  const acceptDisabled = result ? false : !canSubmit;

  return (
    <Dialog
      title="Simulate a credit card purchase"
      onClose={onClose}
      onAccept={handleAccept}
      acceptLabel={acceptLabel}
      cancelLabel={result ? "Close" : "Cancel"}
      acceptDisabled={acceptDisabled}
    >
      {cardsState.kind === "loading" ? (
        <LoadingScreen message="Loading cards…" fullScreen={false} showBranding={false} />
      ) : cardsState.kind === "error" ? (
        <ErrorMessage message={cardsState.message} />
      ) : result ? (
        <div className="flex flex-col gap-ds-3">
          <p className="m-0">Purchase request accepted.</p>
          <div className="flex flex-col gap-ds-1 border-2 border-divider p-ds-3 text-sm">
            <span>
              Status: <strong>{describeStatus(liveStatus)}</strong>
            </span>
            <span className="font-mono text-xs break-all">Request ID: {result.request_id}</span>
          </div>
          {liveStatus === null || liveStatus.status === "pending" ? (
            <LoadingScreen
              message="Waiting for the card service to decide…"
              fullScreen={false}
              showBranding={false}
            />
          ) : liveStatus.status === "declined" ? (
            <ErrorMessage
              message={
                liveStatus.reason ? `Declined — ${liveStatus.reason}` : "Declined."
              }
            />
          ) : (
            <p className="m-0 text-sm">
              Approved: {amount} {currency}
              {parsedInstallments > 1 ? ` in ${parsedInstallments} installments` : ""}.
            </p>
          )}
          <p className="m-0 text-xs text-neutral-600">
            This is the real, live outcome from the card service&apos;s Flink job, delivered over
            the purchase status WebSocket (falling back to a one-shot status check).
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-ds-3">
          <CardSelect value={cardId} onChange={setCardId} cards={cards} />

          <div className="field">
            <Label htmlFor="purchase-amount">Amount</Label>
            <div className="flex gap-ds-2">
              <Input
                id="purchase-amount"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                placeholder="49.99"
                inputMode="decimal"
                autoComplete="off"
              />
              <Select value={currency} onValueChange={setCurrency}>
                <SelectTrigger className="w-24 shrink-0">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CURRENCIES.map((code) => (
                    <SelectItem key={code} value={code}>
                      {code}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="field">
            <Label htmlFor="purchase-description">Description</Label>
            <Input
              id="purchase-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Optional"
              autoComplete="off"
            />
          </div>

          <div className="field">
            <Label htmlFor="purchase-installments">Installments</Label>
            <Input
              id="purchase-installments"
              value={installments}
              onChange={(event) => setInstallments(event.target.value)}
              inputMode="numeric"
              autoComplete="off"
            />
            <span className="text-xs text-neutral-600">
              {MIN_INSTALLMENTS}–{MAX_INSTALLMENTS}
            </span>
          </div>

          {error ? <ErrorMessage message={error} /> : null}
        </div>
      )}
    </Dialog>
  );
}

function describeStatus(status: PurchaseStatus | null): string {
  if (status === null) return "pending";
  return status.status;
}
