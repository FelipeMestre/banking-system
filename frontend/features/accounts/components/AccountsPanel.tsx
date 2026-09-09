"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { DepositDialog } from "@/features/deposits";
import type { DepositResponse } from "@/features/deposits";
import { WithdrawalDialog } from "@/features/withdrawals";
import type { WithdrawalResponse } from "@/features/withdrawals";
import { usePermissions } from "@/lib/auth/usePermissions";
import { currencySymbol, formatAccountNumber, formatCents } from "@/lib/money";
import { AccountsList } from "./AccountsList";
import type { Account } from "../types";

interface DepositOutcome {
  response: DepositResponse;
  account: Account;
}

interface WithdrawalOutcome {
  response: WithdrawalResponse;
  account: Account;
}

function describeDeposit({ response, account }: DepositOutcome): string {
  const symbol = currencySymbol(account.currency);
  return (
    `Deposited ${formatCents(response.amount_applied, symbol)} into ` +
    `${formatAccountNumber(account.account_number)}. New balance: ${formatCents(response.new_balance, symbol)}.`
  );
}

/**
 * A withdrawal only ever reaches here as an approved outcome — `onSuccess`
 * from `WithdrawalDialog` is called only when `response.approved` is true,
 * so `amount_applied`/`new_balance` are guaranteed present. The decline UI
 * (insufficient funds, etc.) lives entirely inside the dialog itself.
 */
function describeWithdrawal({ response, account }: WithdrawalOutcome): string {
  const symbol = currencySymbol(account.currency);
  return (
    `Withdrew ${formatCents(response.amount_applied ?? 0, symbol)} from ` +
    `${formatAccountNumber(account.account_number)}. New balance: ${formatCents(response.new_balance ?? 0, symbol)}.`
  );
}

/**
 * What the Accounts admin tab actually renders: the cross-customer table
 * plus the write:admin-gated Deposit flow. Mirrors CustomersPanel's shape —
 * the action button and its list live together in the owning feature,
 * rather than AdminTabs special-casing this one tab.
 */
export function AccountsPanel() {
  const { hasWriteAdmin } = usePermissions();
  const [depositOpen, setDepositOpen] = useState(false);
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const [outcome, setOutcome] = useState<DepositOutcome | null>(null);
  const [withdrawalOutcome, setWithdrawalOutcome] = useState<WithdrawalOutcome | null>(null);

  return (
    <div className="flex flex-col gap-ds-3">
      {hasWriteAdmin ? (
        <div className="flex justify-end gap-ds-2">
          <Button type="button" variant="outline" onClick={() => setWithdrawOpen(true)}>
            Withdraw
          </Button>
          <Button type="button" onClick={() => setDepositOpen(true)}>
            Deposit
          </Button>
        </div>
      ) : null}

      {outcome ? (
        <div className="flex items-center justify-between rounded-md bg-surface p-ds-3 text-sm">
          <span>{describeDeposit(outcome)}</span>
          <Button type="button" variant="ghost" size="icon" aria-label="Dismiss" onClick={() => setOutcome(null)}>
            ×
          </Button>
        </div>
      ) : null}

      {withdrawalOutcome ? (
        <div className="flex items-center justify-between rounded-md bg-surface p-ds-3 text-sm">
          <span>{describeWithdrawal(withdrawalOutcome)}</span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Dismiss"
            onClick={() => setWithdrawalOutcome(null)}
          >
            ×
          </Button>
        </div>
      ) : null}

      <AccountsList scope="all" refreshToken={refreshToken} />

      {depositOpen ? (
        <DepositDialog
          onClose={() => setDepositOpen(false)}
          onSuccess={(response, account) => {
            setDepositOpen(false);
            setOutcome({ response, account });
            setRefreshToken((token) => token + 1);
          }}
        />
      ) : null}

      {withdrawOpen ? (
        <WithdrawalDialog
          onClose={() => setWithdrawOpen(false)}
          onSuccess={(response, account) => {
            setWithdrawOpen(false);
            setWithdrawalOutcome({ response, account });
            setRefreshToken((token) => token + 1);
          }}
        />
      ) : null}
    </div>
  );
}
