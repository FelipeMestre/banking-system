"use client";

import { Fragment } from "react";
import { AccountCell } from "./AccountCell";
import { TransactionsList } from "@/features/transactions";
import type { AccountSummary } from "@/features/accounts";
import type { Transaction } from "@/features/transactions";

interface Props {
  accounts: AccountSummary[];
  transactionsByAccount: Record<string, Transaction[]>;
  asOf: string;
  /** Controlled: the parent owns which account is selected, since selecting
   * a different account has to trigger a real fetch of that account's
   * transactions (spec §3.3) — a fetch this component has no business
   * starting itself. */
  selectedAccountNumber: string;
  onSelectAccount: (accountNumber: string) => void;
  /**
   * The aside (credit card panel, quick actions, total position) — passed in
   * rather than imported here so those purely-presentational pieces stay
   * server components, rendered by the page, instead of being pulled into
   * this client component's bundle just because they sit next to it.
   */
  aside: React.ReactNode;
}

export function AccountsAndTransactions({
  accounts,
  transactionsByAccount,
  asOf,
  selectedAccountNumber,
  onSelectAccount,
  aside,
}: Props) {
  const firstAccount = accounts[0];

  if (!firstAccount) {
    return <p className="text-neutral-600">No accounts to show.</p>;
  }

  const account = accounts.find((a) => a.account_number === selectedAccountNumber) ?? firstAccount;

  return (
    <>
      <div className="mb-[14px] flex items-baseline justify-between">
        <h6 className="m-0 text-xs">Accounts</h6>
        <span className="text-xs text-neutral-600">Balances as of {asOf}</span>
      </div>

      <div
        className="grid border-2 border-divider border-r-0"
        style={{ gridTemplateColumns: `repeat(${accounts.length}, minmax(0, 1fr))` }}
      >
        {accounts.map((acct) => (
          <AccountCell
            key={acct.account_number}
            account={acct}
            selected={acct.account_number === account.account_number}
            onSelect={() => onSelectAccount(acct.account_number)}
          />
        ))}
      </div>

      <div className="mt-[36px] grid grid-cols-[minmax(0,1fr)_300px] items-start gap-ds-8">
        <TransactionsList
          currencyCode={account.currency}
          transactions={transactionsByAccount[account.account_number] ?? []}
        />
        {/* The key is load-bearing, not decorative: `aside` is JSX authored in
            a Server Component (the page) and handed across into this Client
            Component as a prop. Rendered bare, that crossing makes React's
            dev-mode key check misfire ("Each child in a list should have a
            unique key prop") even though nothing here is a real list —
            wrapping it in a keyed Fragment satisfies the check. */}
        <Fragment key="aside">{aside}</Fragment>
      </div>
    </>
  );
}
