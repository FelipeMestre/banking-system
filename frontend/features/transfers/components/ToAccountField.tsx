"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { RecipientPreview } from "../types";

interface Props {
  value: string;
  onChange: (value: string) => void;
  recipient: RecipientPreview | null;
  isLoading: boolean;
  notFound: boolean;
  error: string | null;
}

export function ToAccountField({ value, onChange, recipient, isLoading, notFound, error }: Props) {
  const trimmed = value.trim();
  const showPreview = trimmed.length >= 6;

  return (
    <div className="flex flex-col gap-ds-1">
      <Label htmlFor="to-account" className="text-[12px] font-normal leading-none text-neutral-700">
        To account number
      </Label>
      <Input
        id="to-account"
        placeholder="Enter the recipient's account number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
        inputMode="numeric"
        className="h-9 min-h-9 rounded-none border border-divider bg-surface px-3 py-2 text-[14px] text-text placeholder:text-neutral-500 shadow-none focus-visible:border-divider focus-visible:ring-0"
      />
      {showPreview ? (
        <div
          data-testid="recipient-preview-live"
          aria-live="polite"
          className="min-h-[40px]"
        >
          {isLoading ? (
            <p className="text-sm text-neutral-600">Looking up account…</p>
          ) : recipient ? (
            <div className="flex items-center gap-ds-2">
              <div className="flex h-[28px] w-[28px] items-center justify-center bg-neutral-200 text-[11px] font-semibold">
                {recipient.initials}
              </div>
              <div className="flex min-w-0 flex-col">
                <span className="truncate text-sm font-semibold">
                  {recipient.name}
                </span>
                <span className="text-[11px] text-neutral-600">
                  •••• {recipient.account_number.slice(-4)} · {recipient.currency}
                </span>
              </div>
            </div>
          ) : error ? (
            <p className="text-sm text-neutral-600">{error}</p>
          ) : notFound ? (
            <p className="text-sm text-neutral-600">No account found</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
