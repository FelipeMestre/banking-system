import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { currencySymbol, formatCents } from "@/lib/money";
import type { Transaction } from "../types";

interface Props {
  transactions: Transaction[];
  currencyCode: string;
}

const DATE_FORMAT = new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short" });

const TYPE_LABEL: Record<Transaction["type"], string> = {
  debit: "Debit",
  credit: "Credit",
  declined: "Declined",
};

/**
 * The selected account's latest transactions (spec §3.3), read straight off
 * the transactions read model — no running balance, description, or
 * reference: the read model does not project those, only what actually moved
 * (`type`, `amount`, `counterparty_account`, `ts`) and, for a decline, why.
 */
export function TransactionsList({ transactions, currencyCode }: Props) {
  const symbol = currencySymbol(currencyCode);

  return (
    <section className="min-w-0">
      <div className="mb-[14px] flex items-baseline justify-between gap-ds-4">
        <h6 className="m-0 text-xs">Latest transactions</h6>
      </div>

      <Table className="tabular-nums">
        <TableHeader>
          <TableRow>
            <TableHead>Date</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Counterparty</TableHead>
            <TableHead className="text-right">Amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {transactions.length === 0 ? (
            <TableRow>
              <TableCell colSpan={4} className="text-neutral-600">
                No movements yet.
              </TableCell>
            </TableRow>
          ) : (
            transactions.map((row) => (
              <TableRow key={row.id}>
                <TableCell className="whitespace-nowrap text-xs text-neutral-700">
                  {DATE_FORMAT.format(new Date(row.ts))}
                </TableCell>
                <TableCell className="text-sm">
                  {TYPE_LABEL[row.type]}
                  {row.type === "declined" && row.decline_reason ? (
                    <span className="ml-[6px] text-[11px] text-neutral-600">({row.decline_reason})</span>
                  ) : null}
                </TableCell>
                <TableCell className="font-mono text-xs whitespace-normal break-all">
                  {row.counterparty_account}
                </TableCell>
                <TableCell className="text-right text-sm font-semibold">
                  {formatCents(row.amount, symbol)}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </section>
  );
}
