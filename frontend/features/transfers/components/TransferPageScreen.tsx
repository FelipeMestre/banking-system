"use client";

import { useTransferDraft } from "../hooks/useTransferDraft";
import { TransferPanel } from "./TransferPanel";
import { InfoAside } from "./InfoAside";
import { ProcessingOverlay } from "./ProcessingOverlay";
import { ResultModal } from "./ResultModal";

export function TransferPageScreen() {
  const draft = useTransferDraft();

  return (
    <div className="flex flex-col gap-ds-4">
      <header className="flex h-[72px] items-center justify-between border-b-2 border-divider bg-surface px-ds-4">
        <h1 className="m-0 font-heading text-[20px] font-extrabold">Send a transfer</h1>
        <div className="flex items-center gap-ds-2">
          <div className="h-[14px] w-[14px] bg-accent" aria-hidden="true" />
          <span className="font-heading text-[16px] font-extrabold tracking-[-0.02em]">
            OpenBank
          </span>
        </div>
      </header>
      <div className="h-[10px] w-full bg-accent" aria-hidden="true" />

      <div className="grid grid-cols-[minmax(0,520px)_1fr] gap-ds-4">
        <TransferPanel draft={draft} />
        <InfoAside />
      </div>

      <ProcessingOverlay isLoading={draft.isLoading} />
      <ResultModal result={draft.result} onClose={draft.reset} />
    </div>
  );
}
