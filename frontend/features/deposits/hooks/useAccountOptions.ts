import { useEffect, useState } from "react";
import { getAllAccounts } from "@/features/accounts/api/get-accounts";
import type { Account } from "@/features/accounts/types";
import { getCustomer } from "@/features/customers/api/get-customer";
import type { Customer } from "@/features/customers/types";

const PAGE_LIMIT = 100;

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; accounts: Account[]; customerById: Map<string, Customer> };

/**
 * Loads one page of every account (the picker filters client-side, there is
 * no backend search endpoint) and resolves each unique `customer_id` on that
 * page via `GET /customers/{id}`, deduped so a page with many accounts per
 * customer only issues one request per customer.
 *
 * No client-side status filter: the backend doesn't reject deposits by
 * account status today, so this doesn't invent a restriction it doesn't
 * enforce — it shows every account and lets the backend stay the source of
 * truth.
 */
export function useAccountOptions() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    getAllAccounts({ limit: PAGE_LIMIT, offset: 0 })
      .then(async (page) => {
        const uniqueCustomerIds = Array.from(new Set(page.items.map((account) => account.customer_id)));
        const customers = await Promise.all(
          uniqueCustomerIds.map((id) =>
            getCustomer(id).catch(() => null),
          ),
        );
        if (cancelled) return;
        const customerById = new Map<string, Customer>();
        uniqueCustomerIds.forEach((id, index) => {
          const customer = customers[index];
          if (customer) customerById.set(id, customer);
        });
        setState({ kind: "ready", accounts: page.items, customerById });
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
  }, []);

  return {
    accounts: state.kind === "ready" ? state.accounts : [],
    customerById: state.kind === "ready" ? state.customerById : new Map<string, Customer>(),
    loading: state.kind === "loading",
    error: state.kind === "error" ? state.message : null,
  };
}
