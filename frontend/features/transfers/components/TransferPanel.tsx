"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ACCOUNTS } from "../fixtures/accounts";
import { useTransferDraft } from "../hooks/useTransferDraft";
import { FromAccountSelect } from "./FromAccountSelect";
import { ToAccountField } from "./ToAccountField";
import { AmountField } from "./AmountField";
import { ExchangeWarningBanner } from "./ExchangeWarningBanner";

type Draft = ReturnType<typeof useTransferDraft>;

interface Props {
  initialFromId?: string;
  draft?: Draft;
}

export function TransferPanel({ initialFromId, draft: externalDraft }: Props) {
  const internalDraft = useTransferDraft();
  const draft = externalDraft ?? internalDraft;

  useEffect(() => {
    if (initialFromId && initialFromId !== draft.fromId) {
      draft.setFromId(initialFromId);
    }
  }, [initialFromId, draft.fromId, draft.setFromId]);

  const effectiveFrom =
    ACCOUNTS.find((a) => a.id === draft.fromId) ?? ACCOUNTS[0] ?? null;

  const symbol = effectiveFrom?.symbol ?? "$";
  const currencyCode = effectiveFrom?.currency ?? "USD";

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

      <FromAccountSelect value={draft.fromId} onChange={draft.setFromId} />
      <ToAccountField value={draft.toNumber} onChange={draft.setToNumber} />
      <AmountField
        value={draft.amount}
        onChange={draft.setAmount}
        symbol={symbol}
        currencyCode={currencyCode}
      />

      {draft.showExchangeWarning && draft.recipient && effectiveFrom ? (
        <ExchangeWarningBanner
          fromCurrency={effectiveFrom.currency}
          toCurrency={draft.recipient.currency}
        />
      ) : null}

      <div className="mt-2 flex flex-col gap-ds-2">
        <Button
          type="submit"
          disabled={!draft.canConfirm}
          className="w-full justify-start rounded-none bg-accent py-3 font-heading text-[14px] font-extrabold tracking-[-0.01em] text-white hover:bg-accent-600 disabled:bg-accent-300 disabled:text-white disabled:opacity-100"
        >
          Confirm transfer
        </Button>
        {draft.showExchangeWarning ? (
          <p className="m-0 text-[11px] leading-5 text-neutral-600">Exchange rate locked at confirmation</p>
        ) : null}
      </div>
    </form>
  );
}
