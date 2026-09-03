import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { RecipientPreview } from "../types";

interface AccountResponse {
  account_number: string;
  currency: string;
  customer_id: string;
}

interface CustomerResponse {
  first_name: string;
  last_name: string;
}

function initialsOf(firstName: string, lastName: string): string {
  return `${firstName[0] ?? ""}${lastName[0] ?? ""}`.toUpperCase();
}

/**
 * Looks up a transfer recipient by account number: GET /accounts/{n} for the
 * currency (needed for the cross-currency warning), then GET /customers/{id}
 * for the name to preview. Returns null only for a real 404 — "this account
 * doesn't exist" — never for a network failure or any other status, so the
 * caller can't confuse "not found" with "something broke".
 */
export async function findRecipient(accountNumber: string): Promise<RecipientPreview | null> {
  const accountResponse = await authorizedFetch(
    `${gatewayOrigin()}/accounts/${encodeURIComponent(accountNumber)}`,
  );
  if (accountResponse.status === 404) return null;
  if (!accountResponse.ok) {
    throw new ApiError(await describeFailure(accountResponse), accountResponse.status);
  }
  const account = (await accountResponse.json()) as AccountResponse;

  const customerResponse = await authorizedFetch(
    `${gatewayOrigin()}/customers/${encodeURIComponent(account.customer_id)}`,
  );
  if (!customerResponse.ok) {
    throw new ApiError(await describeFailure(customerResponse), customerResponse.status);
  }
  const customer = (await customerResponse.json()) as CustomerResponse;

  return {
    account_number: account.account_number,
    currency: account.currency,
    name: `${customer.first_name} ${customer.last_name}`,
    initials: initialsOf(customer.first_name, customer.last_name),
  };
}
