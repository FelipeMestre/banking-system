import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Customer } from "../types";

export async function deleteCustomer(id: string): Promise<Customer> {
  const response = await fetch(`${gatewayOrigin()}/customers/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as Customer;
}
