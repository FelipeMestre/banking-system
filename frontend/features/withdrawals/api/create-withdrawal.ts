import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { WithdrawalRequestBody, WithdrawalResponse } from "../types";

/**
 * Admin cash withdrawal (`POST /admin/withdrawals`, requires write:admin).
 * Synchronous: the response already carries the applied FX (when the
 * withdrawal currency differs from the account's), the resulting balance,
 * or — unlike a deposit — a decline reason (e.g. insufficient funds). A
 * decline is a normal `response.ok` outcome (`approved: false`), so this
 * never throws for one; it only throws via `ApiError` for a genuine
 * network/permission/server failure, exactly like `createDeposit`.
 */
export async function createWithdrawal(body: WithdrawalRequestBody): Promise<WithdrawalResponse> {
  const response = await authorizedFetch(`${gatewayOrigin()}/admin/withdrawals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as WithdrawalResponse;
}
