"use client";

import { Badge } from "@/components/ui/badge";
import { formatDecimalCurrency } from "../format-decimal";
import type { CardAccountListItem } from "../types";

interface Props {
  items: CardAccountListItem[];
  selectedCardAccountId: string | null;
  onSelect: (cardAccountId: string) => void;
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  active: "default",
  blocked: "destructive",
  closed: "secondary",
};

/** Real card list for the logged-in customer (spec: "Real Card List for the
 * Logged-In Customer"). Each tile shows the masked number, expiration,
 * status, and credit_limit — nothing invented, nothing from Phase 4. Laid
 * out as a horizontal card-selector strip (design handoff's "Select a
 * card" section) — no per-card used-credit gauge here, since that figure
 * is only ever fetched for the one currently-selected card account
 * (`CardDetail`'s used-credit-estimate call); showing it on every tile
 * would mean an extra fetch per card, which nothing in this feature does
 * today. */
export function CardList({ items, selectedCardAccountId, onSelect }: Props) {
  if (items.length === 0) {
    return <p className="m-0 text-sm text-neutral-600">You have no credit cards yet.</p>;
  }

  return (
    <ul className="m-0 flex list-none flex-row flex-wrap gap-ds-2 p-0">
      {items.map(({ card_account: cardAccount, card }) => (
        <li key={cardAccount.id} className="min-w-[220px] flex-1">
          <button
            type="button"
            onClick={() => onSelect(cardAccount.id)}
            aria-current={selectedCardAccountId === cardAccount.id ? "true" : undefined}
            className={
              "flex w-full flex-col gap-ds-1 border-2 p-ds-3 text-left " +
              (selectedCardAccountId === cardAccount.id
                ? "border-accent"
                : "border-divider hover:border-neutral-400")
            }
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm tracking-[0.06em]">
                {card ? card.card_number : "No active card"}
              </span>
              <Badge variant={STATUS_VARIANT[cardAccount.status] ?? "secondary"}>
                {cardAccount.status}
              </Badge>
            </div>
            <div className="flex items-center justify-between text-xs text-neutral-600">
              <span>{card ? `Expires ${card.expiration_date}` : ""}</span>
              <span>Limit {formatDecimalCurrency(cardAccount.credit_limit)}</span>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
