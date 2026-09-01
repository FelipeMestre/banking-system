"use client";

import { useCallback, useEffect, useState } from "react";
import { AccountsAndTransactions } from "@/components/home/AccountsAndTransactions";
import { CreditCardPanel } from "@/components/home/CreditCardPanel";
import { CREDIT_CARD, SHOW_CREDIT_CARD } from "@/components/home/credit-card-fixture";
import { QuickActions } from "@/components/home/QuickActions";
import { TotalPosition } from "@/components/home/TotalPosition";
import { getAccounts, totalPositionByCurrency, type Account } from "@/features/accounts";
import { getTransactions, type Transaction } from "@/features/transactions";

const ACCOUNTS_PAGE_SIZE = 50;
const TRANSACTIONS_PAGE_SIZE = 20;

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; accounts: Account[] };

/**
 * Fetches the caller's own accounts (spec §2.1) and, for whichever one is
 * selected, its latest transactions (spec §3.3) — both scoped by
 * `CurrentCustomerDep` server-side, so there is no client-side filtering here.
 */
export function HomeDashboard() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [selectedAccountNumber, setSelectedAccountNumber] = useState<string | null>(null);
  const [transactionsByAccount, setTransactionsByAccount] = useState<Record<string, Transaction[]>>({});

  const refetchAccounts = useCallback(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    getAccounts({ limit: ACCOUNTS_PAGE_SIZE, offset: 0 })
      .then((page) => {
        if (cancelled) return;
        setState({ kind: "ready", accounts: page.items });
        setSelectedAccountNumber((current) => current ?? page.items[0]?.account_number ?? null);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "Could not load accounts.",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => refetchAccounts(), [refetchAccounts]);

  useEffect(() => {
    if (!selectedAccountNumber || selectedAccountNumber in transactionsByAccount) {
      return;
    }
    let cancelled = false;

    getTransactions(selectedAccountNumber, { limit: TRANSACTIONS_PAGE_SIZE })
      .then((page) => {
        if (!cancelled) {
          setTransactionsByAccount((current) => ({ ...current, [selectedAccountNumber]: page.items }));
        }
      })
      .catch(() => {
        // No error surfaced for normal replication lag / a transient failure
        // here — the transactions section just keeps its empty state.
        if (!cancelled) {
          setTransactionsByAccount((current) => ({ ...current, [selectedAccountNumber]: [] }));
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- transactionsByAccount is a cache, not a trigger
  }, [selectedAccountNumber]);

  if (state.kind === "loading") {
    return <p className="m-0 text-[0.9rem] text-neutral-600">Loading your accounts…</p>;
  }

  if (state.kind === "error") {
    return <p className="m-0 text-[0.9rem] text-neutral-600">{state.message}</p>;
  }

  const { accounts } = state;

  if (accounts.length === 0) {
    return (
      <div className="grid grid-cols-[minmax(0,1fr)_300px] items-start gap-ds-8">
        <p className="m-0 text-[0.9rem] text-neutral-600">You have no accounts yet.</p>
        <aside className="flex flex-col gap-[28px]">
          <TotalPosition totals={[]} />
        </aside>
      </div>
    );
  }

  const accountSummaries = accounts.map((account) => ({
    ...account,
    label: `${account.currency} account`,
  }));

  return (
    <AccountsAndTransactions
      accounts={accountSummaries}
      transactionsByAccount={transactionsByAccount}
      asOf="just now"
      selectedAccountNumber={selectedAccountNumber ?? accounts[0]?.account_number ?? ""}
      onSelectAccount={setSelectedAccountNumber}
      aside={
        <aside className="flex flex-col gap-[28px]">
          {SHOW_CREDIT_CARD ? <CreditCardPanel card={CREDIT_CARD} /> : null}
          <QuickActions />
          <TotalPosition totals={totalPositionByCurrency(accounts)} />
        </aside>
      }
    />
  );
}
