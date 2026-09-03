"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { parseAmountToCents } from "@/lib/money";
import { findRecipient } from "../api/find-recipient";
import { getTransferStatus } from "../api/get-transfer-status";
import { requestTransfer } from "../api/request-transfer";
import { watchTransferStatus } from "../api/watch-transfer-status";
import type { Account } from "@/features/accounts";
import type { RecipientPreview, TransferStatus } from "../types";

type RecipientState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "found"; recipient: RecipientPreview }
  | { kind: "not-found" }
  | { kind: "error"; message: string };

export type TransferResult = { kind: "success" } | { kind: "error"; message: string } | null;

function describeError(error: unknown): string {
  if (error instanceof TypeError) {
    return "Could not reach the gateway. Is the stack running?";
  }
  return error instanceof Error ? error.message : "Transfer failed.";
}

/** Maps a ledger verdict onto the flat success/error shape this hook exposes. */
function resultFromStatus(status: TransferStatus): TransferResult {
  if (status.status === "approved") return { kind: "success" };
  if (status.status === "declined") {
    return { kind: "error", message: status.reason ?? "Transfer declined." };
  }
  // A delivered-but-still-"pending" verdict is inconclusive, not a crash.
  return {
    kind: "error",
    message: "We couldn't confirm this transfer yet. Check its status shortly.",
  };
}

export function useTransferDraft(accounts: Account[] = []) {
  const [fromId, setFromId] = useState<string>("");
  const [toNumber, setToNumber] = useState<string>("");
  const [amount, setAmount] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [result, setResult] = useState<TransferResult>(null);
  const [recipientState, setRecipientState] = useState<RecipientState>({ kind: "idle" });

  useEffect(() => {
    const trimmed = toNumber.trim();
    if (trimmed.length < 6) {
      setRecipientState({ kind: "idle" });
      return;
    }
    let cancelled = false;
    setRecipientState({ kind: "loading" });

    findRecipient(trimmed)
      .then((preview) => {
        if (cancelled) return;
        setRecipientState(preview ? { kind: "found", recipient: preview } : { kind: "not-found" });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setRecipientState({ kind: "error", message: describeError(error) });
      });

    return () => {
      cancelled = true;
    };
  }, [toNumber]);

  const recipient = recipientState.kind === "found" ? recipientState.recipient : null;
  const hasRecipient = recipientState.kind === "found";
  const recipientNotFound = recipientState.kind === "not-found";
  const recipientIsLoading = recipientState.kind === "loading";
  const recipientError = recipientState.kind === "error" ? recipientState.message : null;

  const fromAccount = useMemo(
    () => accounts.find((a) => a.account_number === fromId) ?? null,
    [accounts, fromId],
  );

  const showExchangeWarning = useMemo(() => {
    if (!hasRecipient || !fromAccount || !recipient) return false;
    return recipient.currency !== fromAccount.currency;
  }, [hasRecipient, fromAccount, recipient]);

  const canConfirm = useMemo(() => {
    return hasRecipient && amount.trim().length > 0 && !isLoading && result === null;
  }, [hasRecipient, amount, isLoading, result]);

  // Holds the active WebSocket's cleanup so reset()/unmount can stop
  // listening for a verdict on a transfer the user has already left behind.
  const stopWatchingRef = useRef<(() => void) | null>(null);

  const stopWatching = useCallback(() => {
    stopWatchingRef.current?.();
    stopWatchingRef.current = null;
  }, []);

  useEffect(() => stopWatching, [stopWatching]);

  const submit = useCallback(async () => {
    if (!hasRecipient) return;
    const cents = parseAmountToCents(amount);
    if (cents === null) return;

    stopWatching();
    setIsLoading(true);
    setResult(null);

    try {
      const accepted = await requestTransfer({
        source_account: fromId,
        destination_account: toNumber.trim(),
        amount: cents,
      });

      await new Promise<void>((resolve) => {
        stopWatchingRef.current = watchTransferStatus(accepted.request_id, {
          onStatus: (status) => {
            stopWatching();
            setResult(resultFromStatus(status));
            resolve();
          },
          onUnavailable: () => {
            stopWatching();
            // The socket closed without a verdict — fall back to the pull
            // endpoint the gateway offers for exactly this case (spec §6).
            getTransferStatus(accepted.request_id)
              .then((status) => setResult(resultFromStatus(status)))
              .catch((error: unknown) => setResult({ kind: "error", message: describeError(error) }))
              .finally(resolve);
          },
        });
      });
    } catch (error) {
      setResult({ kind: "error", message: describeError(error) });
    } finally {
      setIsLoading(false);
    }
  }, [hasRecipient, amount, fromId, toNumber, stopWatching]);

  const reset = useCallback(() => {
    stopWatching();
    setResult(null);
    setIsLoading(false);
  }, [stopWatching]);

  return {
    fromId,
    toNumber,
    amount,
    isLoading,
    result,
    recipient,
    hasRecipient,
    recipientNotFound,
    recipientIsLoading,
    recipientError,
    showExchangeWarning,
    canConfirm,
    fromAccount,
    setFromId,
    setToNumber,
    setAmount,
    setIsLoading,
    setResult,
    submit,
    reset,
  };
}
