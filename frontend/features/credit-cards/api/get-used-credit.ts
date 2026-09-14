import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { UsedCreditEstimate } from "../types";

/** `GET /card-accounts/{id}/used-credit-estimate`. Always an approximation —
 * see `UsedCreditEstimate.is_estimate` and the spec's race-window note. */
export async function getUsedCredit(cardAccountId: string): Promise<UsedCreditEstimate> {
  const response = await authorizedFetch(
    `${gatewayOrigin()}/card-accounts/${encodeURIComponent(cardAccountId)}/used-credit-estimate`,
  );
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as UsedCreditEstimate;
}
