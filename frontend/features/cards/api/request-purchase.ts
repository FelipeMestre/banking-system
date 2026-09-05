import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { PurchaseAccepted, PurchaseRequestBody } from "../types";

/**
 * `POST /cards/{card_number}/purchases` (Credit Cards Phase 2). The gateway
 * resolves currency conversion server-side (exchange rate, applied_rate) —
 * this only ever sends what `PurchaseRequestDTO` actually accepts.
 */
export async function requestPurchase(
  cardNumber: string,
  body: PurchaseRequestBody,
): Promise<PurchaseAccepted> {
  const response = await authorizedFetch(
    `${gatewayOrigin()}/cards/${encodeURIComponent(cardNumber)}/purchases`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as PurchaseAccepted;
}
