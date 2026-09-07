"use client";

import { Badge } from "@/components/ui/badge";
import { formatCents } from "@/lib/money";
import { availableCents, formatDecimalCurrency } from "../format-decimal";
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

/** Real card list for the logged-in customer; each tile shows masked number,
 * expiration, status, credit_limit, plus compact Used/Avail hint derived from
 * the list payload (no extra fetch). */
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
            <div className="text-xs text-neutral-600">
              {(() => {
                const available = availableCents(cardAccount.credit_limit, cardAccount.used_credit);
                const usedLabel = formatCents(cardAccount.used_credit);
                const availLabel = available === null ? "—" : formatCents(available);
                return `Used ${usedLabel} · Avail ${availLabel}`;
              })()}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
