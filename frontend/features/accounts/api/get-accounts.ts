import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Page } from "@/lib/api/types";
import type { Account } from "../types";

export async function getAccounts(params: { limit: number; offset: number }): Promise<Page<Account>> {
  const query = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  const response = await fetch(`${gatewayOrigin()}/accounts?${query}`);
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as Page<Account>;
}
