"use client";

import { useEffect, useState } from "react";
import { currencySymbol, formatCents } from "@/lib/money";
import { getAccounts } from "../api/get-accounts";
import type { Account } from "../types";

const PAGE_SIZE = 10;

const STATUS_TAG: Record<Account["status"], string> = {
  active: "tag-accent",
  blocked: "tag-outline",
  closed: "tag-neutral",
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
    return <p className="subtitle">Loading accounts…</p>;
  }

  if (state.kind === "error") {
    return <p className="subtitle">{state.message}</p>;
  }

  const { items, total } = state;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);
  const canPrev = offset > 0;
  const canNext = to < total;

  return (
    <div className="flex flex-col gap-ds-3">
      <div className="overflow-x-auto border-2 border-divider">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Account Number</th>
              <th>Currency</th>
              <th>Customer ID</th>
              <th>Branch ID</th>
              <th>Balance</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-neutral-600">
                  No accounts to show.
                </td>
              </tr>
            ) : (
              items.map((account) => (
                <tr key={account.id}>
                  <td className="font-mono text-xs">{account.id}</td>
                  <td className="font-mono text-xs">{account.account_number}</td>
                  <td>{account.currency}</td>
                  <td className="font-mono text-xs">{account.customer_id}</td>
                  <td className="font-mono text-xs">{account.branch_id}</td>
                  <td>{formatCents(account.balance, currencySymbol(account.currency))}</td>
                  <td>
                    <span className={"tag " + STATUS_TAG[account.status]}>{account.status}</span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-neutral-600">
          {total === 0 ? "No accounts" : `Showing ${from}–${to} of ${total}`}
        </span>
        <div className="flex gap-ds-2">
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!canPrev}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!canNext}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
