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
import type { Account } from "@/features/accounts";

interface Props {
  value: string;
  onChange: (value: string) => void;
  accounts: Account[];
}

export function FromAccountSelect({ value, onChange, accounts }: Props) {
  const isDisabled = accounts.length === 0;

  return (
    <div className="flex flex-col gap-ds-1">
      <Label htmlFor="from-account" className="text-[12px] font-normal leading-none text-neutral-700">
        From account
      </Label>
      <Select value={value} onValueChange={onChange} disabled={isDisabled}>
        <SelectTrigger
          id="from-account"
          className="h-9 min-h-9 w-full rounded-none border border-divider bg-surface px-3 py-2 text-[14px] font-normal text-text placeholder:text-neutral-500 focus-visible:border-divider focus-visible:ring-0 data-[placeholder]:text-neutral-500 [&_svg]:text-neutral-600"
        >
          <SelectValue placeholder={isDisabled ? "No accounts available" : "Select account"} />
        </SelectTrigger>
        <SelectContent className="rounded-none border border-divider bg-surface">
          {accounts.map((acc) => {
            const label = `${acc.currency} account`;
            return (
              <SelectItem
                key={acc.account_number}
                value={acc.account_number}
                className="rounded-none text-[14px]"
              >
                {label} {maskAccountNumber(acc.account_number)} · {acc.currency}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
    </div>
  );
}
