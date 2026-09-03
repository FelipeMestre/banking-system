"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Props {
  value: string;
  onChange: (value: string) => void;
  symbol: string;
  currencyCode: string;
}

export function AmountField({ value, onChange, symbol, currencyCode }: Props) {
  return (
    <div className="flex flex-col gap-ds-1">
      <Label htmlFor="amount-field">Amount</Label>
      <div className="relative flex items-center">
        <span className="pointer-events-none absolute left-ds-3 text-sm text-neutral-600">
          {symbol}
        </span>
        <Input
          id="amount-field"
          placeholder="0.00"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete="off"
          inputMode="decimal"
          className="border-2 border-divider pl-ds-6 pr-ds-8 font-heading text-[22px] font-extrabold tabular-nums"
        />
        <span className="pointer-events-none absolute right-ds-3 text-[11px] font-semibold tracking-[0.06em] text-neutral-600">
          {currencyCode}
        </span>
      </div>
    </div>
  );
}
