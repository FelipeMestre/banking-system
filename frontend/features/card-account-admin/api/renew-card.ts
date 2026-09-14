import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { CardIssued, RenewCardRequest } from "../types";

/** `POST /card-accounts/{id}/cards` — rotates the card number + expiry; the
 * old card becomes `replaced`. Returns the new card unmasked. 409 if the
 * account isn't active. */
export async function renewCard(
  cardAccountId: string,
  body: RenewCardRequest = {},
): Promise<CardIssued> {
  const response = await authorizedFetch(`${gatewayOrigin()}/card-accounts/${cardAccountId}/cards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as CardIssued;
}
