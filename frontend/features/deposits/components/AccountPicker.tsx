"use client";

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingScreen } from "@/components/ui/loading-screen";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Account } from "@/features/accounts/types";
import type { Customer } from "@/features/customers/types";
import { currencySymbol, formatAccountNumber, formatCents } from "@/lib/money";
import { useAccountOptions } from "../hooks/useAccountOptions";

interface Props {
  selected: Account | null;
  onSelect: (account: Account) => void;
}

function customerLabel(customerById: Map<string, Customer>, customerId: string): string {
  const customer = customerById.get(customerId);
  return customer ? `${customer.first_name} ${customer.last_name}` : "Unknown customer";
}

/**
 * Presentational account picker for the deposit flow. Shows the real
 * (grouped, not masked) account number alongside the resolved customer name
 * so the admin can confirm they're crediting the right person — filtering is
 * client-side substring match on the account number, over the single page
 * `useAccountOptions` already fetched (no backend search endpoint).
 */
export function AccountPicker({ selected, onSelect }: Props) {
  const { accounts, customerById, loading, error } = useAccountOptions();
  const [filter, setFilter] = useState("");

  const matches = useMemo(() => {
    const needle = filter.trim();
    if (needle.length === 0) return accounts;
    return accounts.filter((account) => account.account_number.includes(needle));
  }, [accounts, filter]);

  if (loading) {
    return <LoadingScreen message="Loading accounts…" fullScreen={false} showBranding={false} />;
  }

  if (error) {
    return <p className="m-0 text-[0.9rem] text-neutral-600">{error}</p>;
  }

  return (
    <div className="flex flex-col gap-ds-2">
      <div className="field">
        <Label htmlFor="deposit-account-filter">Filter by account number</Label>
        <Input
          id="deposit-account-filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          autoComplete="off"
          placeholder="e.g. 1234"
        />
      </div>

      <div className="max-h-60 overflow-y-auto overflow-x-auto border-2 border-divider">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Account Number</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Balance</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {matches.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3} className="text-neutral-600">
                  No accounts match.
                </TableCell>
              </TableRow>
            ) : (
              matches.map((account) => {
                const isSelected = selected?.account_number === account.account_number;
                return (
                  <TableRow
                    key={account.id}
                    aria-selected={isSelected}
                    className={isSelected ? "bg-accent/10 cursor-pointer" : "cursor-pointer"}
                    onClick={() => onSelect(account)}
                  >
                    <TableCell className="font-mono text-xs whitespace-normal break-all">
                      {formatAccountNumber(account.account_number)}
                    </TableCell>
                    <TableCell>{customerLabel(customerById, account.customer_id)}</TableCell>
                    <TableCell>
                      {formatCents(account.balance, currencySymbol(account.currency))}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
