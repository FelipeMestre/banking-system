"use client";

import { formatDecimalCurrency } from "../format-decimal";
import type { CardMovement, Statement } from "../types";

interface Props {
  statement: Statement;
  cycleMovements: CardMovement[];
}

function sumPaymentsMade(movements: CardMovement[]): string {
  // Mirrors `formatDecimalCurrency`'s own `Number(value)` parsing convention
  // for this feature's `Decimal`-as-string wire values — no exact-decimal
  // library is used anywhere else in this module.
  const total = movements
    .filter((movement) => movement.movement_type === "payment")
    .reduce((acc, movement) => acc + Number(movement.amount), 0);
  return total.toFixed(2);
}

/**
 * The selected cycle's totals. `purchases_total`/`interest_total`/
 * `late_fees_total` come straight off the statement itself — authoritative,
 * never re-summed from the movements list, which only ever shows a subset
 * (this cycle's window) and could drift from what `close_statement` actually
 * computed. "Total payments made" is the one figure statements don't store,
 * so it is summed from the cycle-scoped movements instead.
 */
export function StatementTotalsSidebar({ statement, cycleMovements }: Props) {
  const rows: Array<[string, string]> = [
    ["Purchases", formatDecimalCurrency(statement.purchases_total)],
    ["Interest", formatDecimalCurrency(statement.interest_total)],
    ["Late fees", formatDecimalCurrency(statement.late_fees_total)],
    ["Payments made", formatDecimalCurrency(sumPaymentsMade(cycleMovements))],
  ];

  return (
    <aside className="flex flex-col gap-ds-2 border-2 border-divider p-ds-4">
      <dl className="m-0 flex flex-col gap-ds-1">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between text-sm">
            <dt className="text-neutral-600">{label}</dt>
            <dd className="m-0 font-mono tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
