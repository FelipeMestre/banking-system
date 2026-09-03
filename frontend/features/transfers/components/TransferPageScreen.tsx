"use client";

import { useTransferDraft } from "../hooks/useTransferDraft";
import { TransferPanel } from "./TransferPanel";
import { InfoAside } from "./InfoAside";
import { ProcessingOverlay } from "./ProcessingOverlay";
import { ResultModal } from "./ResultModal";

export function TransferPageScreen() {
  const draft = useTransferDraft();

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-bg">
      <header className="flex h-[72px] shrink-0 items-center justify-between border-b-2 border-divider bg-bg px-10">
        <h1 className="m-0 font-heading text-[20px] font-extrabold tracking-[-0.01em]">Send a transfer</h1>
        <div className="flex items-center gap-ds-2">
          <div className="h-[14px] w-[14px] shrink-0 bg-accent" aria-hidden="true" />
          <span className="font-heading text-[19px] font-extrabold tracking-[-0.02em]">OpenBank</span>
        </div>
      </header>
      <div className="h-[10px] w-full shrink-0 bg-accent" aria-hidden="true" />

      <div className="grid flex-1 grid-cols-[minmax(0,520px)_1fr] bg-bg">
        <TransferPanel draft={draft} />
        <InfoAside />
      </div>

      <ProcessingOverlay isLoading={draft.isLoading} />
      <ResultModal result={draft.result} onClose={draft.reset} />
    </div>
  );
}
