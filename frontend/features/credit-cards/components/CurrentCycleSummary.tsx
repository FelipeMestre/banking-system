"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { formatDecimalCurrency } from "../format-decimal";
import type { Statement } from "../types";

interface Props {
  statement: Statement;
  onPay: () => void;
  onDownload: () => void;
  downloading: boolean;
}

/**
 * The selected billing cycle's headline numbers — `total_due`,
 * `minimum_payment`, `period_end` ("closing date"), and `due_date` — read
 * verbatim off the statement the customer picked from
 * `StatementCycleTabs`, plus a real PDF download and a Pay entry point.
 * `credit_balance > 0` (a prior cycle overpaid) is a separate positive-
 * balance banner, not folded into `total_due`.
 */
export function CurrentCycleSummary({ statement, onPay, onDownload, downloading }: Props) {
  const hasCreditBalance = Number(statement.credit_balance) > 0;

  return (
    <section className="flex flex-col gap-ds-3 border-2 border-divider p-ds-4">
      {hasCreditBalance ? (
        <Alert>
          <AlertTitle>Credit balance</AlertTitle>
          <AlertDescription>
            You are carrying a {formatDecimalCurrency(statement.credit_balance)} credit balance from
            a previous cycle — it has already been applied to reduce what you owe.
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid grid-cols-2 gap-ds-3">
        <div>
          <div className="mb-ds-1 font-body text-[10px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
            Total due
          </div>
          <span className="font-heading text-[24px] font-extrabold tracking-[-0.02em] tabular-nums">
            {formatDecimalCurrency(statement.total_due)}
          </span>
        </div>
        <div>
          <div className="mb-ds-1 font-body text-[10px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
            Minimum payment
          </div>
          <span className="font-heading text-[24px] font-extrabold tracking-[-0.02em] tabular-nums">
            {formatDecimalCurrency(statement.minimum_payment)}
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-neutral-600">
        <span>Closing date {statement.period_end}</span>
        <span>Due {statement.due_date}</span>
      </div>

      <div className="flex gap-ds-2">
        <Button type="button" onClick={onPay}>
          Pay
        </Button>
        <Button type="button" variant="outline" onClick={onDownload} disabled={downloading}>
          {downloading ? "Preparing…" : "Download current statement"}
        </Button>
      </div>
    </section>
  );
}
