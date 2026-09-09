"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { formatCycleLabel, formatLongDate } from "../format-date";
import { formatDecimalCurrency } from "../format-decimal";
import { deriveStatementStatusLabel } from "../statement-status";
import type { Statement } from "../types";

interface Props {
  statement: Statement;
  onDownload: () => void;
  downloading: boolean;
  onPay: () => void;
}

interface FieldProps {
  label: string;
  value: string;
  valueClassName?: string;
}

function Field({ label, value, valueClassName }: FieldProps) {
  return (
    <div className="flex flex-col gap-ds-1">
      <span className="font-body text-[10px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
        {label}
      </span>
      <span
        className={`font-heading text-[20px] font-extrabold tracking-[-0.02em] tabular-nums ${valueClassName ?? ""}`}
      >
        {value}
      </span>
    </div>
  );
}

/**
 * The selected billing cycle's headline numbers — `total_due`,
 * `minimum_payment`, `period_end` ("closing date"), and `due_date` — read
 * verbatim off the statement the customer picked from `StatementCycleTabs`,
 * plus Pay and a real PDF download, all inside one bordered card matching
 * the design mock (header row, four-value row with dividers, actions row).
 * `credit_balance > 0` (a prior cycle overpaid) is a separate positive-
 * balance banner, not folded into `total_due`.
 */
export function CurrentCycleSummary({ statement, onDownload, downloading, onPay }: Props) {
  const hasCreditBalance = Number(statement.credit_balance) > 0;

  return (
    <section className="flex flex-col border-2 border-divider">
      {hasCreditBalance ? (
        <div className="p-ds-4 pb-0">
          <Alert>
            <AlertTitle>Credit balance</AlertTitle>
            <AlertDescription>
              You are carrying a {formatDecimalCurrency(statement.credit_balance)} credit balance
              from a previous cycle — it has already been applied to reduce what you owe.
            </AlertDescription>
          </Alert>
        </div>
      ) : null}

      <div className="flex items-baseline justify-between border-b-2 border-divider p-ds-4">
        <span className="font-body text-xs font-bold uppercase tracking-[0.05em]">
          Current cycle — {formatCycleLabel(statement.period_end)}
        </span>
        {deriveStatementStatusLabel(statement) === "Still open" ? (
          <span className="font-body text-xs text-neutral-600">In progress, may still change</span>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-ds-4 border-b-2 border-divider p-ds-4 sm:grid-cols-4">
        <Field label="Total to pay" value={formatDecimalCurrency(statement.total_due)} />
        <div className="border-l-2 border-divider pl-ds-4">
          <Field label="Minimum payment" value={formatDecimalCurrency(statement.minimum_payment)} />
        </div>
        <div className="border-l-2 border-divider pl-ds-4">
          <Field label="Closing date" value={formatLongDate(statement.period_end)} />
        </div>
        <div className="border-l-2 border-divider pl-ds-4">
          <Field
            label="Payment due date"
            value={formatLongDate(statement.due_date)}
            valueClassName="text-accent-700"
          />
        </div>
      </div>

      <div className="flex gap-ds-2 p-ds-4">
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
