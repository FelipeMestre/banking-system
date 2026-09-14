import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Customer } from "../types";

export async function deleteCustomer(id: string): Promise<Customer> {
  const response = await authorizedFetch(`${gatewayOrigin()}/customers/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Customer;
}
