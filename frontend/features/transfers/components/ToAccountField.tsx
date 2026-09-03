"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DIRECTORY } from "../fixtures/directory";
import { findRecipient } from "../hooks/useTransferDraft";

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export function ToAccountField({ value, onChange }: Props) {
  const trimmed = value.trim();
  const showPreview = trimmed.length >= 6;
  const recipient = showPreview ? (findRecipient(value) ?? null) : null;
  const notFound = showPreview && recipient === null;

  return (
    <div className="flex flex-col gap-ds-1">
      <Label htmlFor="to-account">To account</Label>
      <Input
        id="to-account"
        placeholder="Enter the recipient's account number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
        inputMode="numeric"
      />
      {showPreview ? (
        <div
          data-testid="recipient-preview-live"
          aria-live="polite"
          className="min-h-[40px]"
        >
          {recipient ? (
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
          ) : notFound ? (
            <p className="text-sm text-neutral-600">No account found</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
