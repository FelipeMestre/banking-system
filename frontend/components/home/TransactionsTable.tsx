import { currencySymbol, formatCents } from "@/lib/money";
import type { Transaction } from "@/lib/types";

interface Props {
  accountLabel: string;
  currencyCode: string;
  transactions: Transaction[];
}

const DATE_FORMAT = new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short" });

/** Appending a local midnight time avoids the one-day-back shift `new
 * Date("2026-08-24")` gets in timezones west of UTC, where a bare ISO date
 * string is parsed as UTC midnight rather than local midnight. */
function formatShortDate(iso: string): string {
  return DATE_FORMAT.format(new Date(`${iso}T00:00:00`));
}

/**
 * The transactions table for the selected account.
 *
 * `transactions` already carries each row's post-movement balance
 * (`balanceCents`) — a real read model would compute and return that
 * per-row; deriving it client-side from the account's current balance is
 * only correct for this placeholder fixture, per the bound design's own
 * caveat ("in production this must come from the read model").
 */
export function TransactionsTable({ accountLabel, currencyCode, transactions }: Props) {
  const symbol = currencySymbol(currencyCode);
  const total = transactions.length;

  return (
    <section className="min-w-0">
      <div className="mb-[14px] flex items-baseline justify-between gap-ds-4">
        <h6 className="m-0 text-xs">Latest transactions — {accountLabel}</h6>
        <a href="#" className="font-heading text-xs font-semibold text-accent">
          All activity
        </a>
      </div>

      <table className="table tabular-nums">
        <thead>
          <tr>
            <th className="border-b-2 border-divider py-0 pr-[12px] pb-[10px] text-left text-[10px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
              Date
            </th>
            <th className="border-b-2 border-divider py-0 pr-[12px] pb-[10px] text-left text-[10px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
              Description
            </th>
            <th className="whitespace-nowrap border-b-2 border-divider py-0 pr-[12px] pb-[10px] text-right text-[10px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
              Credit
            </th>
            <th className="whitespace-nowrap border-b-2 border-divider py-0 pr-[12px] pb-[10px] text-right text-[10px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
              Debit
            </th>
            <th className="whitespace-nowrap border-b-2 border-divider py-0 pb-[10px] pl-[12px] text-right text-[10px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
              Balance
            </th>
          </tr>
        </thead>
        <tbody>
          {transactions.length === 0 ? (
            <tr>
              <td colSpan={5} className="border-b border-neutral-300 py-[13px] text-[13px] text-neutral-600">
                No movements in the last 90 days
              </td>
            </tr>
          ) : (
            transactions.map((row) => (
              <tr key={row.id}>
                <td className="whitespace-nowrap border-b border-neutral-300 py-[13px] pr-[12px] align-top text-xs text-neutral-700">
                  {formatShortDate(row.date)}
                </td>
                <td className="border-b border-neutral-300 py-[13px] pr-[12px] align-top text-sm">
                  <div className="font-semibold">{row.description}</div>
                  <div className="mt-[2px] text-[11px] tracking-[0.04em] text-neutral-600">{row.reference}</div>
                </td>
                <td className="whitespace-nowrap border-b border-neutral-300 py-[13px] pr-[12px] text-right align-top text-sm font-semibold text-neutral-900">
                  {row.creditCents ? formatCents(row.creditCents, symbol) : <span aria-hidden>—</span>}
                </td>
                <td className="whitespace-nowrap border-b border-neutral-300 py-[13px] pr-[12px] text-right align-top text-sm font-semibold text-accent-700">
                  {row.debitCents ? formatCents(row.debitCents, symbol) : <span aria-hidden>—</span>}
                </td>
                <td className="whitespace-nowrap border-b border-neutral-300 py-[13px] pl-[12px] text-right align-top text-[13px] text-neutral-700">
                  {formatCents(row.balanceCents, symbol)}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      <div className="mt-[14px] flex items-center justify-between gap-ds-4 text-xs text-neutral-600">
        <span>
          Showing {transactions.length} of {total} movements
        </span>
        <span className="tracking-[0.04em]">Cleared balances only · Pending items excluded</span>
      </div>
    </section>
  );
}
