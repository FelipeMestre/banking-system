import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";

/** The logged-in customer's own identity, via the existing `GET /customers/me`
 * (already built — no new backend endpoint). Resolving this first is how
 * `getCardAccounts` gets the `customer_id` `GET /card-accounts?customer_id=`
 * requires. */
export interface CurrentCustomer {
  id: string;
}

export async function getCurrentCustomer(): Promise<CurrentCustomer> {
  const response = await authorizedFetch(`${gatewayOrigin()}/customers/me`);
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as CurrentCustomer;
}
