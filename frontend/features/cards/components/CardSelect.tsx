"use client";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { maskAccountNumber } from "@/lib/money";
import type { CardListItem } from "../types";

interface Props {
  value: string;
  onChange: (value: string) => void;
  cards: CardListItem[];
}

export function CardSelect({ value, onChange, cards }: Props) {
  const isDisabled = cards.length === 0;

  return (
    <div className="field">
      <Label htmlFor="purchase-card">Card</Label>
      <Select value={value} onValueChange={onChange} disabled={isDisabled}>
        <SelectTrigger id="purchase-card" className="w-full">
          <SelectValue placeholder={isDisabled ? "No cards available" : "Select a card"} />
        </SelectTrigger>
        <SelectContent>
          {cards.map((card) => (
            <SelectItem key={card.id} value={card.id}>
              {card.customer_name} — {maskAccountNumber(card.card_number)} · {card.status}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
