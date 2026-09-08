import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Page } from "@/lib/api/types";
import type { Account } from "../types";

export async function getAccounts(params: { limit: number; offset: number }): Promise<Page<Account>> {
  const query = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  const response = await authorizedFetch(`${gatewayOrigin()}/accounts?${query}`);
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Page<Account>;
}

export async function getAllAccounts(params: { limit: number; offset: number }): Promise<Page<Account>> {
  const query = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  const response = await authorizedFetch(`${gatewayOrigin()}/accounts/all?${query}`);
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Page<Account>;
}

export async function getAllAccountsForCustomer(params: {
  customerId: string;
  limit: number;
  offset: number;
}): Promise<Page<Account>> {
  const query = new URLSearchParams({
    customer_id: params.customerId,
    limit: String(params.limit),
    offset: String(params.offset),
  });
  const response = await authorizedFetch(`${gatewayOrigin()}/accounts/all?${query}`);
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Page<Account>;
}
