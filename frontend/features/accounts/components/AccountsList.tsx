"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { currencySymbol, formatCents } from "@/lib/money";
import { getAccounts } from "../api/get-accounts";
import type { Account } from "../types";

const PAGE_SIZE = 10;

// "blocked" keeps the accent-colored outline `.tag-outline` used to have —
// shadcn's own `outline` Badge variant is a plain neutral border, so the
// accent color is painted back on top rather than dropped.
const STATUS_BADGE: Record<Account["status"], { variant: "default" | "secondary" | "outline"; className?: string }> = {
  active: { variant: "default" },
  blocked: { variant: "outline", className: "border-accent text-accent" },
  closed: { variant: "secondary" },
};

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; items: Account[]; total: number };

export function AccountsList() {
  const [offset, setOffset] = useState(0);
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    getAccounts({ limit: PAGE_SIZE, offset })
      .then((page) => {
        if (!cancelled) setState({ kind: "ready", items: page.items, total: page.total });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "Could not load accounts.",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [offset]);

  if (state.kind === "loading") {
    return <p className="m-0 text-[0.9rem] text-neutral-600">Loading accounts…</p>;
  }

  if (state.kind === "error") {
    return <p className="m-0 text-[0.9rem] text-neutral-600">{state.message}</p>;
  }

  const { items, total } = state;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);
  const canPrev = offset > 0;
  const canNext = to < total;

  return (
    <div className="flex flex-col gap-ds-3">
      <div className="overflow-x-auto border-2 border-divider">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Account Number</TableHead>
              <TableHead>Currency</TableHead>
              <TableHead>Customer ID</TableHead>
              <TableHead>Branch ID</TableHead>
              <TableHead>Balance</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-neutral-600">
                  No accounts to show.
                </TableCell>
              </TableRow>
            ) : (
              items.map((account) => (
                <TableRow key={account.id}>
                  <TableCell className="font-mono text-xs whitespace-normal break-all">{account.id}</TableCell>
                  <TableCell className="font-mono text-xs whitespace-normal break-all">{account.account_number}</TableCell>
                  <TableCell>{account.currency}</TableCell>
                  <TableCell className="font-mono text-xs whitespace-normal break-all">{account.customer_id}</TableCell>
                  <TableCell className="font-mono text-xs whitespace-normal break-all">{account.branch_id}</TableCell>
                  <TableCell>{formatCents(account.balance, currencySymbol(account.currency))}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_BADGE[account.status].variant} className={STATUS_BADGE[account.status].className}>
                      {account.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-neutral-600">
          {total === 0 ? "No accounts" : `Showing ${from}–${to} of ${total}`}
        </span>
        <div className="flex gap-ds-2">
          <Button
            type="button"
            variant="outline"
            disabled={!canPrev}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={!canNext}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
