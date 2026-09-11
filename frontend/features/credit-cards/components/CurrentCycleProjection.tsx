"use client";

import { Button } from "@/components/ui/button";
import { formatLongDate } from "../format-date";
import { formatDecimalCurrency } from "../format-decimal";
import type { CurrentCycleProjection as CurrentCycleProjectionData } from "../types";

interface Props {
  projection: CurrentCycleProjectionData;
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
 * The genuinely live, uncommitted current cycle (spec: "No naming collision
 * between live and closed-statement views") — recomputed fresh on every
 * fetch, never cached. `overdue_from_previous_cycle`/`interest_on_overdue`
 * are rendered ONLY when present: an absent field means "not overdue (yet)",
 * which is a different fact from "$0 overdue" and must never collapse into a
 * zero placeholder (spec's own explicit acceptance criterion). This view is
 * always payable — unlike `SelectedStatementSummary`, there is no due-date
 * gate on the live cycle.
 */
export function CurrentCycleProjection({ projection, onPay }: Props) {
  const hasOverdue = projection.overdue_from_previous_cycle !== null;

  return (
    <section className="flex flex-col border-2 border-divider">
      <div className="flex items-baseline justify-between border-b-2 border-divider p-ds-4">
        <span className="font-body text-xs font-bold uppercase tracking-[0.05em]">
          Current cycle — projected close {formatLongDate(projection.projected_period_end)}
        </span>
        <span className="font-body text-xs text-neutral-600">In progress, may still change</span>
      </div>

      <div className="grid grid-cols-2 gap-ds-4 border-b-2 border-divider p-ds-4 sm:grid-cols-4">
        {hasOverdue ? (
          <>
            <Field
              label="Overdue from previous cycle"
              value={formatDecimalCurrency(projection.overdue_from_previous_cycle!)}
              valueClassName="text-accent-700"
            />
            <div className="border-l-2 border-divider pl-ds-4">
              <Field
                label="Interest on overdue"
                value={formatDecimalCurrency(projection.interest_on_overdue!)}
                valueClassName="text-accent-700"
              />
            </div>
          </>
        ) : null}
        <div className={hasOverdue ? "border-l-2 border-divider pl-ds-4" : ""}>
          <Field label="New purchases this cycle" value={formatDecimalCurrency(projection.new_purchases_this_cycle)} />
        </div>
        <div className="border-l-2 border-divider pl-ds-4">
          <Field label="Total to pay" value={formatDecimalCurrency(projection.total_to_pay)} />
        </div>
      </div>

      <div className="flex gap-ds-2 p-ds-4">
        <Button type="button" onClick={onPay}>
          Pay
        </Button>
      </div>
    </section>
  );
}
