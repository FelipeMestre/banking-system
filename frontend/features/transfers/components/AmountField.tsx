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
      <Label htmlFor="amount-field" className="text-[12px] font-normal leading-none text-neutral-700">
        Amount
      </Label>
      <div className="flex items-center gap-ds-2 border-2 border-divider bg-surface px-3.5 focus-within:border-divider focus-within:ring-0">
        <span className="shrink-0 font-heading text-[15px] font-extrabold leading-none text-neutral-700">
          {symbol}
        </span>
        <Input
          id="amount-field"
          placeholder="0.00"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete="off"
          inputMode="decimal"
          className="h-auto min-h-0 flex-1 rounded-none border-0 bg-transparent px-[10px] py-[14px] font-heading text-[22px] font-extrabold tabular-nums text-text placeholder:text-neutral-500 shadow-none focus-visible:border-0 focus-visible:ring-0 focus-visible:outline-none"
        />
        <span className="shrink-0 text-[12px] font-semibold tracking-[0.06em] text-neutral-600">
          {currencyCode}
        </span>
      </div>
    </div>
  );
}
