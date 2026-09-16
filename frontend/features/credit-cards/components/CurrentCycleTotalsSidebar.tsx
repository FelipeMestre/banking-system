"use client";

import { formatDecimalCurrency } from "../format-decimal";
import type { CardMovement } from "../types";

interface Props {
  /** Exactly the rows rendered in the movements table above this sidebar —
   * real movements AND the synthetic carried-balance/interest rows
   * (`buildCarryForwardMovements`) — never re-fetched or recomputed from
   * anything else. */
  movements: CardMovement[];
}

const INCREASE_TYPES: readonly CardMovement["movement_type"][] = [
  "purchase", "fee", "interest", "late_fee", "carried_balance",
];
const DECREASE_TYPES: readonly CardMovement["movement_type"][] = ["payment", "refund"];

function sumsByType(movements: CardMovement[]): Partial<Record<CardMovement["movement_type"], number>> {
  const sums: Partial<Record<CardMovement["movement_type"], number>> = {};
  for (const movement of movements) {
    sums[movement.movement_type] = (sums[movement.movement_type] ?? 0) + Number(movement.amount);
  }
  return sums;
}

/**
 * The current, still-open cycle's totals — unlike `StatementTotalsSidebar`
 * (a closed statement's authoritative, backend-stored figures), every number
 * here is summed directly from the SAME movements array the table above it
 * renders, so a payment reflects here the instant it lands in that table.
 *
 * Deliberately separate from `CurrentCycleProjection`'s own "Total to pay":
 * that figure is `current_cycle_projection_service.py`'s stable, month-level
 * accrual (purchases + carried-forward balance + interest) and never nets out
 * a payment made mid-cycle by design — it represents what accrued, not what's
 * left owing right now. "Left to pay" here is the answer to that second
 * question, purely from what this table shows.
 *
 * One known divergence from the backend's own `new_purchases_this_cycle`:
 * an installment purchase's movement row carries its FULL original amount,
 * not the per-cycle installment due amount the projection adds instead — so
 * "Purchases" here can read higher than the projection's own figure for a
 * card with open installment plans. Accepted rather than hidden: this panel
 * exists to show exactly what's in the table, not to reproduce that formula.
 */
export function CurrentCycleTotalsSidebar({ movements }: Props) {
  const sums = sumsByType(movements);
  const amountFor = (type: CardMovement["movement_type"]) => sums[type] ?? 0;

  const totalIncreases = INCREASE_TYPES.reduce((acc, type) => acc + amountFor(type), 0);
  const totalDecreases = DECREASE_TYPES.reduce((acc, type) => acc + amountFor(type), 0);
  const leftToPay = Math.max(0, totalIncreases - totalDecreases);

  const rows: Array<[string, number]> = (
    [
      ["Purchases", amountFor("purchase")],
      ["Carried from previous cycle", amountFor("carried_balance")],
      ["Interest", amountFor("interest")],
      ["Fees", amountFor("fee") + amountFor("late_fee")],
      ["Refunds", amountFor("refund")],
    ] satisfies Array<[string, number]>
  ).filter(([, amount]) => amount > 0);

  rows.push(["Payments made", amountFor("payment")]);

  return (
    <aside className="flex flex-col gap-ds-2 border-2 border-divider p-ds-4">
      <dl className="m-0 flex flex-col gap-ds-1">
        {rows.map(([label, amount]) => (
          <div key={label} className="flex items-center justify-between text-sm">
            <dt className="text-neutral-600">{label}</dt>
            <dd className="m-0 font-mono tabular-nums">{formatDecimalCurrency(amount.toFixed(2))}</dd>
          </div>
        ))}
        <div className="mt-ds-1 flex items-center justify-between border-t-2 border-divider pt-ds-2 text-sm font-bold">
          <dt>Left to pay</dt>
          <dd className="m-0 font-mono tabular-nums">{formatDecimalCurrency(leftToPay.toFixed(2))}</dd>
        </div>
      </dl>
    </aside>
  );
}
