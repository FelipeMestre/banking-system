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
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  accounts: Account[];
}

/**
 * Picks one of the caller's own accounts — shared across any flow that debits
 * or credits a specific account (transfers' "From account", paying a credit
 * card, ...). Not entity-specific to one feature, so it lives here rather
 * than inside a single domain's `components/` (per the feature-oriented
 * architecture's own promotion rule: reused across features -> `components/`).
 */
export function AccountSelect({ id, label, value, onChange, accounts }: Props) {
  const isDisabled = accounts.length === 0;

  return (
    <div className="flex flex-col gap-ds-1">
      <Label htmlFor={id} className="text-[12px] font-normal leading-none text-neutral-700">
        {label}
      </Label>
      <Select value={value} onValueChange={onChange} disabled={isDisabled}>
        <SelectTrigger
          id={id}
          className="h-9 min-h-9 w-full rounded-none border border-divider bg-surface px-3 py-2 text-[14px] font-normal text-text placeholder:text-neutral-500 focus-visible:border-divider focus-visible:ring-0 data-[placeholder]:text-neutral-500 [&_svg]:text-neutral-600"
        >
          <SelectValue placeholder={isDisabled ? "No accounts available" : "Select account"} />
        </SelectTrigger>
        <SelectContent className="rounded-none border border-divider bg-surface">
          {accounts.map((acc) => {
            const accountLabel = `${acc.currency} account`;
            return (
              <SelectItem
                key={acc.account_number}
                value={acc.account_number}
                className="rounded-none text-[14px]"
              >
                {accountLabel} {maskAccountNumber(acc.account_number)} · {acc.currency}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
    </div>
  );
}
