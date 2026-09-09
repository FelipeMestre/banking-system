"use client";

import { useEffect, useState } from "react";
import { CreditCard } from "lucide-react";
import { formatCents } from "@/lib/money";
import { DS_ICON_PROPS } from "@/lib/icon-props";
import {
  availableCents,
  creditLimitDecimalToCents,
  getCardAccounts,
  getCurrentCustomer,
  type CardAccountListItem,
} from "@/features/credit-cards";

const CARD_ACCOUNTS_PAGE_SIZE = 50;

type State =
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "ready"; item: CardAccountListItem };

/** The card with the highest credit limit wins the default spot on the
 * homepage — the customer's single most significant line of credit. */
function pickBiggestLimit(items: CardAccountListItem[]): CardAccountListItem | null {
  return items.reduce<CardAccountListItem | null>((best, item) => {
    if (best === null) return item;
    const bestCents = creditLimitDecimalToCents(best.card_account.credit_limit) ?? -Infinity;
    const itemCents = creditLimitDecimalToCents(item.card_account.credit_limit) ?? -Infinity;
    return itemCents > bestCents ? item : best;
  }, null);
}

/**
 * The customer's highest-limit credit card, with real data off
 * `GET /card-accounts` (`features/credit-cards`) — no invented card entity
 * or fixture. Renders nothing while loading, on error, or when the customer
 * has no cards: this is a secondary homepage widget, not content the rest
 * of the page depends on.
 */
export function CreditCardPanel() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    getCurrentCustomer()
      .then((customer) =>
        getCardAccounts({ customerId: customer.id, limit: CARD_ACCOUNTS_PAGE_SIZE, offset: 0 }),
      )
      .then((page) => {
        if (cancelled) return;
        const biggest = pickBiggestLimit(page.items);
        setState(biggest ? { kind: "ready", item: biggest } : { kind: "empty" });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: "empty" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind !== "ready") return null;

  const { card_account: cardAccount, card } = state.item;
  const totalCents = creditLimitDecimalToCents(cardAccount.credit_limit) ?? 0;
  const availableCentsValue = availableCents(cardAccount.credit_limit, cardAccount.used_credit) ?? totalCents;
  const usedCents = totalCents - availableCentsValue;
  const utilisationPercent = totalCents > 0 ? Math.round((usedCents / totalCents) * 100) : 0;

  return (
    <section>
      <h6 className="mb-[14px] text-xs">Credit card</h6>
      <div className="flex flex-col gap-[18px] border-2 border-divider p-[20px]">
        <div className="flex items-start justify-between gap-ds-3">
          <div className="flex h-[36px] w-[54px] flex-none items-center justify-center bg-text text-bg">
            <CreditCard size={26} {...DS_ICON_PROPS} />
          </div>
          <div className="text-right">
            <div className="mt-[4px] text-xs tracking-[0.06em] text-neutral-600 tabular-nums">
              {card?.card_number ?? "—"}
            </div>
          </div>
        </div>

        <div>
          <div className="mb-ds-2 font-body text-[10px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
            Available limit
          </div>
          <div className="flex items-baseline gap-[5px]">
            <span className="font-heading text-[15px] font-extrabold text-neutral-700">$</span>
            <span className="font-heading text-[32px] font-extrabold leading-none tracking-[-0.03em] tabular-nums">
              {formatCents(availableCentsValue, "")}
            </span>
          </div>
        </div>

        <div className="h-[2px] bg-neutral-300">
          <div className="h-[2px] bg-accent" style={{ width: `${utilisationPercent}%` }} />
        </div>

        <div className="flex items-center justify-between text-xs text-neutral-600 tabular-nums">
          <span>{formatCents(usedCents)} used</span>
          <span>of {formatCents(totalCents)}</span>
        </div>
      </div>
    </section>
  );
}
