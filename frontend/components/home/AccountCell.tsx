"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { currencySymbol, formatAccountNumber, formatCents } from "@/lib/money";
import type { AccountSummary } from "@/features/accounts";

interface Props {
  account: AccountSummary;
  selected: boolean;
  onSelect: () => void;
  /** Whether the balance and account number show in the clear, or masked. */
  showDetails: boolean;
}

const COPIED_RESET_MS = 1500;

/**
 * One cell of the accounts strip. Selection is expressed only by the 4px
 * accent bar across the top — no other selected styling, per the design.
 *
 * The border-right is unconditional on every cell, including the last one:
 * the containing grid has no right border of its own, so the last cell's
 * own border-right becomes the frame's right edge. That's what keeps the
 * internal dividers and the outer frame the same 2px weight without
 * special-casing "last cell".
 *
 * The outer element is a `role="button"` div, not a native `<button>`: it
 * now contains the copy button below, and nesting an interactive `<button>`
 * inside another is invalid HTML — the browser silently hoists the inner one
 * out, breaking both layout and click semantics. `tabIndex`/`onKeyDown`
 * restore the native button's keyboard behavior (Enter/Space activates it).
 */
export function AccountCell({ account, selected, onSelect, showDetails }: Props) {
  const symbol = currencySymbol(account.currency);
  const [copied, setCopied] = useState(false);

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect();
    }
  }

  function handleCopy(event: React.MouseEvent) {
    // Selecting an account is this cell's own click behavior — the copy
    // button sits inside it, so its click must not bubble up and select.
    event.stopPropagation();
    void navigator.clipboard.writeText(account.account_number).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), COPIED_RESET_MS);
    });
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={handleKeyDown}
      className="block cursor-pointer border-r-2 border-divider bg-transparent p-0 text-left font-body text-text hover:bg-neutral-200"
    >
      <div className={`h-[4px] ${selected ? "bg-accent" : "bg-transparent"}`} />
      <div className="flex flex-col gap-[14px] px-[20px] pt-[18px] pb-[20px]">
        <div className="flex items-center justify-between gap-ds-3">
          <span className="font-body text-[11px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
            {account.label}
          </span>
          <span className="font-body text-[11px] font-semibold tracking-[0.08em] text-neutral-600">
            {account.currency}
          </span>
        </div>

        <div className="flex items-baseline gap-[6px]">
          <span className="font-heading text-[16px] font-extrabold text-neutral-700">{symbol}</span>
          <span className="font-heading text-[34px] font-extrabold leading-none tracking-[-0.03em] tabular-nums">
            {showDetails ? formatCents(account.balance, "") : "••••••"}
          </span>
        </div>

        <div className="flex items-center justify-between gap-ds-3 text-xs text-neutral-600">
          <div className="flex min-w-0 items-center gap-1">
            <span className="tracking-[0.04em] tabular-nums">
              {showDetails ? formatAccountNumber(account.account_number) : "•••• ••••"}
            </span>
            <button
              type="button"
              onClick={handleCopy}
              disabled={!showDetails}
              aria-label={showDetails ? "Copy account number" : "Reveal the account number to copy it"}
              title={showDetails ? "Copy account number" : "Reveal the account number to copy it"}
              className="flex size-5 shrink-0 items-center justify-center rounded-none text-neutral-600 hover:text-text disabled:cursor-not-allowed disabled:opacity-40"
            >
              {copied ? <Check size={13} /> : <Copy size={13} />}
            </button>
          </div>
          <span>{account.status === "active" ? "Active" : account.status}</span>
        </div>
      </div>
    </div>
  );
}
