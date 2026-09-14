import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { DepositRequestBody, DepositResponse } from "../types";

/**
 * Admin cash deposit (`POST /admin/deposits`, requires write:admin).
 * Synchronous: the response already carries the applied FX (when the
 * deposit currency differs from the account's) and the resulting balance.
 */
export async function createDeposit(body: DepositRequestBody): Promise<DepositResponse> {
  const response = await authorizedFetch(`${gatewayOrigin()}/admin/deposits`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as DepositResponse;
}
