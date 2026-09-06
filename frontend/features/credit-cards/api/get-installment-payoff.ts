import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { InstallmentPayoff } from "../types";

/** `GET /card-accounts/{id}/installment-payoff` — the "settle all
 * installment balances early" amount. Safe to expose verbatim: installments
 * carry 0% interest, so this is a plain sum, never a guessed figure. */
export async function getInstallmentPayoff(cardAccountId: string): Promise<InstallmentPayoff> {
  const response = await authorizedFetch(
    `${gatewayOrigin()}/card-accounts/${encodeURIComponent(cardAccountId)}/installment-payoff`,
  );
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as InstallmentPayoff;
}
