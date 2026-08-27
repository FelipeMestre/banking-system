import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Customer } from "../types";

export interface UpdateCustomerBody {
  identification_number?: string;
  first_name?: string;
  last_name?: string;
  date_of_birth?: string;
  gender?: string | null;
  active?: boolean;
}

export async function updateCustomer(id: string, body: UpdateCustomerBody): Promise<Customer> {
  const response = await fetch(`${gatewayOrigin()}/customers/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as Customer;
}
