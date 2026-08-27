"use client";

import { useCallback, useEffect, useState } from "react";
import { TransferForm } from "./TransferForm";
import { TransferOutcome } from "./TransferOutcome";
import { getTransferStatus } from "../api/get-transfer-status";
import { requestTransfer } from "../api/request-transfer";
import { watchTransferStatus } from "../api/watch-transfer-status";
import type { Phase, TransferRequestBody, TransferStatus } from "../types";

export function TransferConsole() {
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });

  // Only a pending transfer is worth watching, and a plain string keeps the
  // effect's dependencies stable across re-renders.
  const watchedRequestId = phase.kind === "pending" ? phase.requestId : null;

  const applyStatus = useCallback((requestId: string, status: TransferStatus) => {
    setPhase((current) => {
      // A verdict for an abandoned transfer must not overwrite the current one.
      if (!isWatching(current, requestId)) return current;
      if (status.status === "approved") return { kind: "approved", requestId, status };
      if (status.status === "declined") return { kind: "declined", requestId, status };
      return { kind: "unresolved", requestId };
    });
  }, []);

  useEffect(() => {
    if (watchedRequestId === null) return;

    return watchTransferStatus(watchedRequestId, {
      onStatus: (status) => applyStatus(watchedRequestId, status),
      onUnavailable: () => {
        // The socket never delivered anything. Fall back to the pull endpoint
        // the gateway offers for exactly this case (§6).
        void getTransferStatus(watchedRequestId)
          .then((status) => applyStatus(watchedRequestId, status))
          .catch((error: unknown) =>
            setPhase({ kind: "error", message: describe(error) }),
          );
      },
    });
  }, [watchedRequestId, applyStatus]);

  const submit = useCallback((body: TransferRequestBody) => {
    setPhase({ kind: "submitting" });
    void requestTransfer(body)
      .then((accepted) =>
        setPhase({
          kind: "pending",
          requestId: accepted.request_id,
          feeAmount: accepted.fee_amount,
          amount: body.amount,
        }),
      )
      .catch((error: unknown) => setPhase({ kind: "error", message: describe(error) }));
  }, []);

  const recheck = useCallback(
    (requestId: string) => {
      void getTransferStatus(requestId)
        .then((status) => {
          if (status.status === "pending") return;
          setPhase(
            status.status === "approved"
              ? { kind: "approved", requestId, status }
              : { kind: "declined", requestId, status },
          );
        })
        .catch((error: unknown) => setPhase({ kind: "error", message: describe(error) }));
    },
    [],
  );

  const busy = phase.kind === "submitting" || phase.kind === "pending";

  return (
    <>
      <TransferForm disabled={busy} onSubmit={submit} />
      <TransferOutcome
        phase={phase}
        onRecheck={recheck}
        onReset={() => setPhase({ kind: "idle" })}
      />
    </>
  );
}

function isWatching(phase: Phase, requestId: string): boolean {
  return phase.kind === "pending" && phase.requestId === requestId;
}

function describe(error: unknown): string {
  if (error instanceof TypeError) {
    return "Could not reach the gateway. Is the stack running?";
  }
  return error instanceof Error ? error.message : "Unexpected error.";
}
