import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Customer } from "../types";

export interface CreateCustomerBody {
  identification_number: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string | null;
}

export async function createCustomer(body: CreateCustomerBody): Promise<Customer> {
  const response = await authorizedFetch(`${gatewayOrigin()}/customers`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Customer;
}
