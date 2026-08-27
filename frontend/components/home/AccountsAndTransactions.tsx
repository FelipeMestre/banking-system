"use client";

import { Fragment, useState } from "react";
import { AccountCell } from "./AccountCell";
import { TransactionsTable } from "./TransactionsTable";
import type { AccountSummary } from "@/lib/placeholder-home";
import type { Transaction } from "@/lib/types";

interface Props {
  accounts: AccountSummary[];
  transactionsByAccount: Record<string, Transaction[]>;
  asOf: string;
  /**
   * The aside (credit card panel, quick actions, total position) — passed in
   * rather than imported here so those purely-presentational pieces stay
   * server components, rendered by the page, instead of being pulled into
   * this client component's bundle just because they sit next to it.
   */
  aside: React.ReactNode;
}

/**
 * Owns the one real interaction on this screen: which account is selected.
 * The accounts strip and the transactions table below it both react to the
 * same selection, so the state has to live above both of them — same
 * pattern as `TransferConsole` owning `Phase` for its child form/outcome.
 */
export function AccountsAndTransactions({ accounts, transactionsByAccount, asOf, aside }: Props) {
  const [selected, setSelected] = useState(0);
  const firstAccount = accounts[0];

  if (!firstAccount) {
    return <p className="text-neutral-600">No accounts to show.</p>;
  }

  // `selected` only ever moves to indexes AccountCell.onSelect hands it, which
  // only ever come from mapping over this same `accounts` array — but that
  // isn't visible to the type checker, so fall back to the account already
  // proven to exist above rather than asserting the index is always in range.
  const account = accounts[selected] ?? firstAccount;

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
        {accounts.map((acct, index) => (
          <AccountCell
            key={acct.account_number}
            account={acct}
            selected={index === selected}
            onSelect={() => setSelected(index)}
          />
        ))}
      </div>

      <div className="mt-[36px] grid grid-cols-[minmax(0,1fr)_300px] items-start gap-ds-8">
        <TransactionsTable
          accountLabel={account.label}
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
