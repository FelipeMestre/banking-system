"use client";

import { CheckCircle2, Lock, XCircle, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDecimalCurrency } from "../format-decimal";
import type { CardMovement } from "../types";

interface Props {
  items: CardMovement[];
}

// UTC, not the viewer's local zone: `occurred_at` is an instant, and a
// midnight-UTC movement must not read as "yesterday" west of Greenwich.
const DATE_FORMAT = new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short", timeZone: "UTC" });

const TYPE_LABEL: Record<CardMovement["movement_type"], string> = {
  purchase: "Purchase",
  payment: "Payment",
  fee: "Fee",
  interest: "Interest",
  refund: "Refund",
  declined: "Declined",
  late_fee: "Late fee",
};

// A movement without its own description still needs a title — this is what
// renders when the customer (or a simulated purchase) left it blank.
const DEFAULT_TITLE: Record<CardMovement["movement_type"], string> = {
  purchase: "Card purchase",
  payment: "Payment received",
  fee: "Card fee",
  interest: "Interest charge",
  refund: "Refund received",
  declined: "Attempted purchase",
  late_fee: "Late fee",
};

type Tone = "increase" | "decrease" | "declined";

// Purchases/fees/interest increase what is owed; payments/refunds reduce it —
// the same classification the backend's used-credit-estimate endpoint sums
// by. A declined movement never happened, so it gets its own neutral tone
// instead of either sign. A late fee is billed the same way a card fee is —
// it increases what is owed, same as any other charge.
const TONE: Record<CardMovement["movement_type"], Tone> = {
  purchase: "increase",
  fee: "increase",
  interest: "increase",
  payment: "decrease",
  refund: "decrease",
  declined: "declined",
  late_fee: "increase",
};

const ICON: Record<CardMovement["movement_type"], LucideIcon> = {
  purchase: Lock,
  fee: Lock,
  interest: Lock,
  payment: CheckCircle2,
  refund: CheckCircle2,
  declined: XCircle,
  late_fee: Lock,
};

const TONE_CLASSES: Record<Tone, { icon: string; box: string; amount: string }> = {
  increase: { icon: "text-destructive", box: "border-destructive/30", amount: "text-destructive" },
  decrease: { icon: "text-text", box: "border-divider", amount: "text-text" },
  declined: { icon: "text-neutral-400", box: "border-divider", amount: "text-neutral-400" },
};

/**
 * Type-specific movement display (spec: "Type-Specific Movement Display").
 * A tone-matched icon and amount color separate what happened at a glance —
 * approved purchases/fees/interest in red (owed goes up), payments/refunds
 * in the base text color with a leading "+" (owed goes down), declined
 * attempts muted and struck through. FX rows show the original amount and
 * applied rate; installment purchases carry their plan as a small pill next
 * to the title.
 */
export function MovementsList({ items }: Props) {
  if (items.length === 0) {
    return <p className="m-0 text-sm text-neutral-600">No movements yet.</p>;
  }

  return (
    <ul className="m-0 flex list-none flex-col border-2 border-divider p-0">
      {items.map((movement, index) => {
        const tone = TONE[movement.movement_type];
        const classes = TONE_CLASSES[tone];
        const Icon = ICON[movement.movement_type];
        const title = movement.description || DEFAULT_TITLE[movement.movement_type];
        const showPlus = tone === "decrease";
        const hasInstallments = !!movement.installment_count && movement.installment_count > 1;

        return (
          <li
            key={movement.id}
            className={cn(
              "flex items-center gap-ds-3 p-ds-4",
              index > 0 && "border-t-2 border-divider",
              tone === "declined" && "text-neutral-500",
            )}
          >
            <div
              className={cn(
                "flex size-10 shrink-0 items-center justify-center border-2",
                classes.box,
              )}
            >
              <Icon className={cn("size-5", classes.icon)} />
            </div>

            <div className="flex min-w-0 flex-1 flex-col gap-ds-1">
              <div className="flex flex-wrap items-center gap-ds-2">
                <span className="font-heading text-[15px] font-bold">{title}</span>
                {hasInstallments ? (
                  <span className="border-2 border-destructive/40 px-ds-2 py-[1px] text-xs font-semibold text-destructive">
                    Installment 1 of {movement.installment_count}
                  </span>
                ) : null}
              </div>

              <p className="m-0 text-sm text-neutral-600">
                {DATE_FORMAT.format(new Date(movement.occurred_at))}
                {hasInstallments && movement.installment_amount
                  ? ` · ${formatDecimalCurrency(movement.installment_amount)} each`
                  : ""}
              </p>

              {tone === "declined" && movement.decline_reason ? (
                <p className="m-0 text-xs text-neutral-500">Reason: {movement.decline_reason}</p>
              ) : null}

              {movement.fx_pair && movement.fx_applied_rate ? (
                <p className="m-0 text-xs text-neutral-600">
                  {movement.fx_pair} · rate {movement.fx_applied_rate}
                </p>
              ) : null}
            </div>

            <div className="flex shrink-0 flex-col items-end gap-ds-1">
              <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-neutral-500">
                {TYPE_LABEL[movement.movement_type]}
              </span>
              <span
                className={cn(
                  "font-heading text-[16px] font-extrabold tabular-nums",
                  classes.amount,
                  tone === "declined" && "line-through",
                )}
              >
                {showPlus ? "+" : ""}
                {formatDecimalCurrency(movement.amount)}
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
