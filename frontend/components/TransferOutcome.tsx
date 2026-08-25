"use client";

import { formatCents } from "@/lib/money";
import type { Phase } from "@/lib/types";

interface Props {
  phase: Phase;
  onRecheck: (requestId: string) => void;
  onReset: () => void;
}

export function TransferOutcome({ phase, onRecheck, onReset }: Props) {
  if (phase.kind === "idle") return null;

  return (
    <section className="card outcome" aria-live="polite">
      {renderBody(phase, onRecheck, onReset)}
    </section>
  );
}

function renderBody(phase: Phase, onRecheck: Props["onRecheck"], onReset: Props["onReset"]) {
  switch (phase.kind) {
    case "submitting":
      return <p className="status status-pending">Submitting…</p>;

    case "pending":
      return (
        <>
          <p className="status status-pending">Processing…</p>
          <p className="detail">
            Sending {formatCents(phase.amount)} plus a {formatCents(phase.feeAmount)} fee. Waiting
            for the ledger to decide.
          </p>
          <RequestId value={phase.requestId} />
        </>
      );

    case "approved":
      return (
        <>
          <p className="status status-approved">approved ✅</p>
          <RequestId value={phase.requestId} />
          <RestartButton onReset={onReset} />
        </>
      );

    case "declined":
      return (
        <>
          <p className="status status-declined">
            declined ❌ {phase.status.reason ? `(${phase.status.reason})` : null}
          </p>
          <RequestId value={phase.requestId} />
          <RestartButton onReset={onReset} />
        </>
      );

    case "unresolved":
      return (
        <>
          <p className="status status-pending">Still pending</p>
          <p className="detail">
            The gateway stopped waiting before the ledger answered. The transfer may still settle.
          </p>
          <RequestId value={phase.requestId} />
          <button type="button" onClick={() => onRecheck(phase.requestId)}>
            Check again
          </button>
        </>
      );

    case "error":
      return (
        <>
          <p className="status status-declined">Something went wrong</p>
          <p className="detail">{phase.message}</p>
          <RestartButton onReset={onReset} />
        </>
      );
  }
}

function RequestId({ value }: { value: string }) {
  return (
    <p className="detail">
      request_id <code>{value}</code>
    </p>
  );
}

function RestartButton({ onReset }: { onReset: () => void }) {
  return (
    <button type="button" onClick={onReset}>
      New transfer
    </button>
  );
}
