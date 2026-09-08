import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { CardAccount } from "@/features/credit-cards/types";
import type { UpdateCreditLimitRequest } from "../types";

/** `PUT /card-accounts/{id}` — only updates `credit_limit` when present. */
export async function updateCreditLimit(
  cardAccountId: string,
  body: UpdateCreditLimitRequest,
): Promise<CardAccount> {
  const response = await authorizedFetch(`${gatewayOrigin()}/card-accounts/${cardAccountId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as CardAccount;
}
