import { currencySymbol, formatCents, maskAccountNumber } from "@/lib/money";
import type { AccountSummary } from "@/features/accounts";

interface Props {
  account: AccountSummary;
  selected: boolean;
  onSelect: () => void;
}

/**
 * One cell of the accounts strip. Selection is expressed only by the 4px
 * accent bar across the top — no other selected styling, per the design.
 *
 * The border-right is unconditional on every cell, including the last one:
 * the containing grid has no right border of its own, so the last cell's
 * own border-right becomes the frame's right edge. That's what keeps the
 * internal dividers and the outer frame the same 2px weight without
 * special-casing "last cell".
 */
export function AccountCell({ account, selected, onSelect }: Props) {
  const symbol = currencySymbol(account.currency);

  return (
    <button
      type="button"
      onClick={onSelect}
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
            {formatCents(account.balance, "")}
          </span>
        </div>

        <div className="flex items-center justify-between gap-ds-3 text-xs text-neutral-600">
          <span className="tracking-[0.04em] tabular-nums">{maskAccountNumber(account.account_number)}</span>
          <span>{account.status === "active" ? "Active" : account.status}</span>
        </div>
      </div>
    </button>
  );
}
