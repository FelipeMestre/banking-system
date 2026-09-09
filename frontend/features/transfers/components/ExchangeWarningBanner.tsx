"use client";

import { AlertTriangle } from "lucide-react";

interface Props {
  fromCurrency: string;
  toCurrency: string;
}

export function ExchangeWarningBanner({ fromCurrency, toCurrency }: Props) {
  return (
    <div className="flex gap-ds-3 border-2 bg-neutral-200 p-[14px_16px] text-sm">
      <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600" />
      <div className="flex flex-col gap-ds-1">
        <p className="m-0 inline bg-[#fef3c7] px-1 text-sm">
          This transfer moves {fromCurrency} into {toCurrency} — exchange rate applies.
        </p>
      </div>
    </div>
  );
}
