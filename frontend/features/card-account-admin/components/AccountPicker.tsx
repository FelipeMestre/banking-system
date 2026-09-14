"use client";

import { useEffect, useState } from "react";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getAllAccountsForCustomer } from "@/features/accounts/api/get-accounts";
import type { Account } from "@/features/accounts/types";

/** Mirrors `CustomerPicker.tsx`'s state machine: a plain shadcn `Select`
 * populated by a single page of `getAllAccountsForCustomer`. Kept
 * intentionally simple — no search/typeahead — since one customer's account
 * roster is expected to be small enough for one page; revisit with a
 * combobox if that stops being true. Re-fetches whenever `customerId`
 * changes, since the same dialog instance can be reused across customers. */
const ACCOUNT_PAGE_SIZE = 200;

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; accounts: Account[] };

function accountLabel(account: Account): string {
  return `${account.account_number} — ${account.currency}`;
}

export function AccountPicker({
  customerId,
  value,
  onChange,
}: {
  customerId: string;
  value: string | null;
  onChange: (accountId: string) => void;
}) {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    getAllAccountsForCustomer({ customerId, limit: ACCOUNT_PAGE_SIZE, offset: 0 })
      .then((page) => {
        if (!cancelled) setState({ kind: "ready", accounts: page.items });
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
  }, [customerId]);

  const isEmpty = state.kind === "ready" && state.accounts.length === 0;

  return (
    <div className="field">
      <Label htmlFor="account-picker">Paying account</Label>
      {state.kind === "error" ? (
        <p className="m-0 text-xs text-accent-700">{state.message}</p>
      ) : isEmpty ? (
        <p className="m-0 text-xs text-neutral-600">No accounts for this customer.</p>
      ) : (
        <Select
          value={value ?? ""}
          onValueChange={onChange}
          disabled={state.kind === "loading"}
        >
          <SelectTrigger id="account-picker" className="w-full">
            <SelectValue
              placeholder={state.kind === "loading" ? "Loading accounts…" : "Select an account"}
            />
          </SelectTrigger>
          <SelectContent>
            {state.kind === "ready"
              ? state.accounts.map((account) => (
                  <SelectItem key={account.id} value={account.id}>
                    {accountLabel(account)}
                  </SelectItem>
                ))
              : null}
          </SelectContent>
        </Select>
      )}
    </div>
  );
}
