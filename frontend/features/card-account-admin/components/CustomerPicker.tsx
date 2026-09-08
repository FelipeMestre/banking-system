"use client";

import { useEffect, useState } from "react";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getCustomers } from "@/features/customers/api/get-customers";
import type { Customer } from "@/features/customers/types";

/** No customer-picker component pre-existed in this codebase (checked
 * `features/branches` and `features/locations` — neither has a select-by-id
 * pattern), so this is new: a plain shadcn `Select` populated by a single
 * page of `getCustomers`. Kept intentionally simple — no search/typeahead —
 * since the admin customer roster is expected to be small enough for one
 * page; revisit with a combobox if that stops being true. */
const CUSTOMER_PAGE_SIZE = 200;

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; customers: Customer[] };

function customerLabel(customer: Customer): string {
  return `${customer.first_name} ${customer.last_name} (${customer.identification_number})`;
}

export function CustomerPicker({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (customerId: string) => void;
}) {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    getCustomers({ limit: CUSTOMER_PAGE_SIZE, offset: 0 })
      .then((page) => {
        if (!cancelled) setState({ kind: "ready", customers: page.items });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "Could not load customers.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="field">
      <Label htmlFor="customer-picker">Customer</Label>
      {state.kind === "error" ? (
        <p className="m-0 text-xs text-accent-700">{state.message}</p>
      ) : (
        <Select
          value={value ?? ""}
          onValueChange={onChange}
          disabled={state.kind === "loading"}
        >
          <SelectTrigger id="customer-picker" className="w-full">
            <SelectValue
              placeholder={state.kind === "loading" ? "Loading customers…" : "Select a customer"}
            />
          </SelectTrigger>
          <SelectContent>
            {state.kind === "ready"
              ? state.customers.map((customer) => (
                  <SelectItem key={customer.id} value={customer.id}>
                    {customerLabel(customer)}
                  </SelectItem>
                ))
              : null}
          </SelectContent>
        </Select>
      )}
    </div>
  );
}
