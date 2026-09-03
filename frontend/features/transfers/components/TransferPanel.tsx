"use client";

import { useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { currencySymbol } from "@/lib/money";
import type { Account } from "@/features/accounts";
import { useTransferDraft } from "../hooks/useTransferDraft";
import { FromAccountSelect } from "./FromAccountSelect";
import { ToAccountField } from "./ToAccountField";
import { AmountField } from "./AmountField";
import { ExchangeWarningBanner } from "./ExchangeWarningBanner";

type Draft = ReturnType<typeof useTransferDraft>;

interface Props {
  initialFromId?: string;
  draft?: Draft;
  accounts?: Account[];
  isLoadingAccounts?: boolean;
  accountsError?: string | null;
}

export function TransferPanel({
  initialFromId,
  draft: externalDraft,
  accounts = [],
  isLoadingAccounts = false,
  accountsError = null,
}: Props) {
  const internalDraft = useTransferDraft(accounts);
  const draft = externalDraft ?? internalDraft;

  useEffect(() => {
    if (initialFromId && initialFromId !== draft.fromId) {
      draft.setFromId(initialFromId);
    }
  }, [initialFromId, draft.fromId, draft.setFromId]);

  const effectiveFrom = useMemo(() => {
    if (draft.fromId) {
      return accounts.find((a) => a.account_number === draft.fromId) ?? null;
    }
    return accounts[0] ?? null;
  }, [accounts, draft.fromId]);

  const symbol = effectiveFrom ? currencySymbol(effectiveFrom.currency) : "$";
  const currencyCode = effectiveFrom?.currency ?? "USD";

  const showExchangeWarning = Boolean(
    draft.hasRecipient &&
      draft.recipient &&
      effectiveFrom &&
      draft.recipient.currency !== effectiveFrom.currency,
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void draft.submit();
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-7 border-r-2 border-divider bg-bg p-10"
    >
      <p className="m-0 text-[13px] leading-6 text-neutral-600">
        Move funds between your accounts or to another OpenBank customer. Transfers within OpenBank
        are immediate.
      </p>

      <FromAccountSelect value={draft.fromId} onChange={draft.setFromId} accounts={accounts} />
      <ToAccountField
        value={draft.toNumber}
        onChange={draft.setToNumber}
        recipient={draft.recipient}
        isLoading={draft.recipientIsLoading}
        notFound={draft.recipientNotFound}
        error={draft.recipientError}
      />
      <AmountField
        value={draft.amount}
        onChange={draft.setAmount}
        symbol={symbol}
        currencyCode={currencyCode}
      />

      {accountsError ? (
        <p className="m-0 text-[0.9rem] text-neutral-600">{accountsError}</p>
      ) : null}
      {isLoadingAccounts ? (
        <p className="m-0 text-[0.9rem] text-neutral-600">Loading accounts…</p>
      ) : null}
      {accounts.length === 0 && !isLoadingAccounts && !accountsError ? (
        <p className="m-0 text-[0.9rem] text-neutral-600">No accounts to show</p>
      ) : null}

      {showExchangeWarning && draft.recipient && effectiveFrom ? (
        <ExchangeWarningBanner
          fromCurrency={effectiveFrom.currency}
          toCurrency={draft.recipient.currency}
        />
      ) : null}

      <div className="mt-2 flex flex-col gap-ds-2">
        <Button
          type="submit"
          disabled={!draft.canConfirm || accounts.length === 0}
          className="w-full justify-start rounded-none bg-accent py-3 font-heading text-[14px] font-extrabold tracking-[-0.01em] text-white hover:bg-accent-600 disabled:bg-accent-300 disabled:text-white disabled:opacity-100"
        >
          Confirm transfer
        </Button>
        {showExchangeWarning ? (
          <p className="m-0 text-[11px] leading-5 text-neutral-600">Exchange rate locked at confirmation</p>
        ) : null}
      </div>
    </form>
  );
}
