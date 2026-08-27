import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Page } from "@/lib/api/types";
import type { Customer } from "../types";

export async function getCustomers(params: { limit: number; offset: number }): Promise<Page<Customer>> {
  const query = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  const response = await fetch(`${gatewayOrigin()}/customers?${query}`);
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as Page<Customer>;
}
