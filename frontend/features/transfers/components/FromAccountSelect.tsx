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
import { ACCOUNTS } from "../fixtures/accounts";

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export function FromAccountSelect({ value, onChange }: Props) {
  return (
    <div className="flex flex-col gap-ds-1">
      <Label htmlFor="from-account" className="text-[12px] font-normal leading-none text-neutral-700">
        From account
      </Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger
          id="from-account"
          className="h-9 min-h-9 w-full rounded-none border border-divider bg-surface px-3 py-2 text-[14px] font-normal text-text placeholder:text-neutral-500 focus-visible:border-divider focus-visible:ring-0 data-[placeholder]:text-neutral-500 [&_svg]:text-neutral-600"
        >
          <SelectValue placeholder="Select account" />
        </SelectTrigger>
        <SelectContent className="rounded-none border border-divider bg-surface">
          {ACCOUNTS.map((acc) => (
            <SelectItem key={acc.id} value={acc.id} className="rounded-none text-[14px]">
              {acc.label} {maskAccountNumber(acc.account_number)} · {acc.currency}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
