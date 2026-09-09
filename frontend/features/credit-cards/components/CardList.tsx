"use client";

import { Badge } from "@/components/ui/badge";
import { formatCents } from "@/lib/money";
import { formatDecimalCurrency, formatExpiry, usagePercent } from "../format-decimal";
import type { CardAccountListItem } from "../types";

interface Props {
  items: CardAccountListItem[];
  selectedCardAccountId: string | null;
  onSelect: (cardAccountId: string) => void;
}

const STATUS_LABEL: Record<string, string> = {
  active: "Active",
  blocked: "Blocked",
  closed: "Closed",
};

// "Active" gets the app's own accent tint (a positive, brand-colored
// signal); "blocked"/"closed" get a plain outline — no variant here reaches
// for `destructive`, which is reserved for an actually alarming state.
const STATUS_BADGE_CLASS: Record<string, string> = {
  active: "border-accent/30 bg-accent/10 text-accent",
  blocked: "border-border bg-transparent text-foreground",
  closed: "border-border bg-transparent text-foreground",
};

/** Real card list for the logged-in customer: masked number, expiration,
 * status, and a usage bar (used against limit) derived from the list
 * payload alone (no extra fetch). The selected card is marked with a top
 * accent bar rather than a full-border highlight. */
export function CardList({ items, selectedCardAccountId, onSelect }: Props) {
  if (items.length === 0) {
    return <p className="m-0 text-sm text-neutral-600">You have no credit cards yet.</p>;
  }

  return (
    <ul className="m-0 flex list-none flex-row flex-wrap gap-ds-3 p-0">
      {items.map(({ card_account: cardAccount, card }) => {
        const isSelected = selectedCardAccountId === cardAccount.id;
        const percent = usagePercent(cardAccount.credit_limit, cardAccount.used_credit);

        return (
          <li key={cardAccount.id} className="w-[280px] flex-none">
            <button
              type="button"
              onClick={() => onSelect(cardAccount.id)}
              aria-current={isSelected ? "true" : undefined}
              className={
                "relative hover:cursor-pointer hover:bg-neutral-200 flex w-full flex-col gap-ds-3 overflow-hidden border-2 border-divider p-ds-4 pt-[18px] text-left hover:border-neutral-400 " +
                (isSelected ? "bg-neutral-200" : "bg-neutral-100")
              }
            >
              <span
                aria-hidden="true"
                className={"absolute inset-x-0 top-0 h-1 " + (isSelected ? "bg-accent" : "bg-transparent")}
              />

              <div className="flex items-center justify-between gap-ds-2">
                <span className="font-mono text-base font-bold tracking-[0.04em]">
                  {card ? card.card_number : "No active card"}
                </span>
                <Badge className={STATUS_BADGE_CLASS[cardAccount.status] ?? STATUS_BADGE_CLASS.closed}>
                  {STATUS_LABEL[cardAccount.status] ?? cardAccount.status}
                </Badge>
              </div>

              <span className="text-xs text-neutral-600">
                {card ? `Exp ${formatExpiry(card.expiration_date)}` : ""}
              </span>

              <div className="h-1.5 w-full bg-neutral-300">
                <div className="h-1.5 bg-accent" style={{ width: `${percent}%` }} />
              </div>

              <div className="flex items-baseline justify-between gap-ds-2">
                <span className="font-heading text-xl font-extrabold tabular-nums">
                  {formatCents(cardAccount.used_credit)}
                </span>
                <span className="text-xs whitespace-nowrap text-neutral-600">
                  used of {formatDecimalCurrency(cardAccount.credit_limit)}
                </span>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
