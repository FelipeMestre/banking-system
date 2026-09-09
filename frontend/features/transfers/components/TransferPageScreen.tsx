"use client";

import { useCallback, useEffect, useState } from "react";
import { LoadingScreen } from "@/components/ui/loading-screen";
import { getAccounts, type Account } from "@/features/accounts";
import { ApiError } from "@/lib/api/client";
import { useTransferDraft } from "../hooks/useTransferDraft";
import { TransferPanel } from "./TransferPanel";
import { InfoAside } from "./InfoAside";
import { ProcessingOverlay } from "./ProcessingOverlay";
import { ResultModal } from "./ResultModal";

const ACCOUNTS_PAGE_SIZE = 50;

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; accounts: Account[] };

export function TransferPageScreen() {
  const [state, setState] = useState<State>({ kind: "loading" });

  const accounts = state.kind === "ready" ? state.accounts : [];
  const draft = useTransferDraft(accounts);

  const refetch = useCallback(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    getAccounts({ limit: ACCOUNTS_PAGE_SIZE, offset: 0 })
      .then((page) => {
        if (cancelled) return;
        setState({ kind: "ready", accounts: page.items });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ kind: "ready", accounts: [] });
          return;
        }
        setState({
          kind: "error",
          message: error instanceof Error ? error.message : "Could not load accounts.",
        });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => refetch(), [refetch]);

  useEffect(() => {
    if (state.kind === "ready" && state.accounts.length > 0 && !draft.fromId) {
      const first = state.accounts[0];
      if (first) draft.setFromId(first.account_number);
    }
  }, [state, draft.fromId, draft.setFromId]);

  let leftPanel: React.ReactNode;
  if (state.kind === "loading") {
    leftPanel = (
      <div className="border-r-2 border-divider bg-bg p-10">
        <LoadingScreen message="Loading your accounts" fullScreen={false} showBranding={false} />
      </div>
    );
  } else if (state.kind === "error") {
    leftPanel = (
      <div className="border-r-2 border-divider bg-bg p-10">
        <p className="m-0 text-[0.9rem] text-neutral-600">{state.message}</p>
      </div>
    );
  } else {
    leftPanel = <TransferPanel draft={draft} accounts={accounts} />;
  }

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
        {leftPanel}
        <InfoAside />
      </div>

      <ProcessingOverlay isLoading={draft.isLoading} />
      <ResultModal result={draft.result} onClose={draft.reset} />
    </div>
  );
}
