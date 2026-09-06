"use client";

import { Badge } from "@/components/ui/badge";
import { formatDecimalCurrency } from "../format-decimal";
import type { CardMovement } from "../types";

interface Props {
  items: CardMovement[];
}

const TYPE_LABEL: Record<CardMovement["movement_type"], string> = {
  purchase: "Purchase",
  payment: "Payment",
  fee: "Fee",
  interest: "Interest",
  refund: "Refund",
  declined: "Declined",
};

// Purchases/fees/interest increase what is owed; payments/refunds reduce it —
// the sign shown here mirrors the same classification the backend's
// used-credit-estimate endpoint sums by.
const INCREASES_BALANCE = new Set<CardMovement["movement_type"]>(["purchase", "fee", "interest"]);

/**
 * Type-specific movement display (spec: "Type-Specific Movement Display").
 * Purchases and payments are visually distinguished; declined rows show the
 * decline reason; FX rows show the original amount and applied rate;
 * installment rows show their position.
 */
export function MovementsList({ items }: Props) {
  if (items.length === 0) {
    return <p className="m-0 text-sm text-neutral-600">No movements yet.</p>;
  }

  return (
    <ul className="m-0 flex list-none flex-col gap-ds-2 p-0">
      {items.map((movement) => {
        const isDeclined = movement.movement_type === "declined";
        const sign = INCREASES_BALANCE.has(movement.movement_type) ? "+" : "-";
        return (
          <li
            key={movement.id}
            className={
              "flex flex-col gap-ds-1 border-2 p-ds-3 " +
              (isDeclined ? "border-divider text-neutral-500" : "border-divider")
            }
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-ds-2">
                <Badge variant={isDeclined ? "destructive" : "secondary"}>
                  {TYPE_LABEL[movement.movement_type]}
                </Badge>
                {movement.description ? (
                  <span className="text-sm">{movement.description}</span>
                ) : null}
              </div>
              <span
                className={
                  "font-mono text-sm tabular-nums " + (isDeclined ? "line-through" : "")
                }
              >
                {`${isDeclined ? "" : sign}${formatDecimalCurrency(movement.amount)}`}
              </span>
            </div>

            {isDeclined && movement.decline_reason ? (
              <p className="m-0 text-xs text-neutral-600">Declined — {movement.decline_reason}</p>
            ) : null}

            {movement.fx_pair && movement.fx_applied_rate ? (
              <p className="m-0 text-xs text-neutral-600">
                {movement.fx_pair} · rate {movement.fx_applied_rate}
              </p>
            ) : null}

            {movement.installment_count && movement.installment_count > 1 ? (
              <p className="m-0 text-xs text-neutral-600">
                Installment 1 of {movement.installment_count}
                {movement.installment_amount
                  ? ` · ${formatDecimalCurrency(movement.installment_amount)} each`
                  : ""}
              </p>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
