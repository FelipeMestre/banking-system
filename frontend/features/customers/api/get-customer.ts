import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Customer } from "../types";

/** Single-customer lookup (`GET /customers/{id}`, requires read:admin). */
export async function getCustomer(id: string): Promise<Customer> {
  const response = await authorizedFetch(`${gatewayOrigin()}/customers/${id}`);
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Customer;
}
