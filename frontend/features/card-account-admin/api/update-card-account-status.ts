import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { CardAccount } from "@/features/credit-cards/types";
import type { UpdateCardAccountStatusRequest } from "../types";

/** `POST /card-accounts/{id}/status` — block/unblock/close the account.
 * Closing is balance-guarded server-side (409 `CardAccountNotCloseableError`
 * with a human-readable `detail`/`error.message` when the balance is > 0);
 * callers must surface that message rather than a generic failure. */
export async function updateCardAccountStatus(
  cardAccountId: string,
  body: UpdateCardAccountStatusRequest,
): Promise<CardAccount> {
  const response = await authorizedFetch(
    `${gatewayOrigin()}/card-accounts/${cardAccountId}/status`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as CardAccount;
}
