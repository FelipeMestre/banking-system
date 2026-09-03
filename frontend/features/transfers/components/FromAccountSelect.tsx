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
      <Label htmlFor="from-account">From account</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id="from-account" className="w-full">
          <SelectValue placeholder="Select account" />
        </SelectTrigger>
        <SelectContent>
          {ACCOUNTS.map((acc) => (
            <SelectItem key={acc.id} value={acc.id}>
              {acc.label} {maskAccountNumber(acc.account_number)} · {acc.currency}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
