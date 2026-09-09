import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { CardPaymentAccepted, CardPaymentRequestBody } from "../types";

/** `POST /card-accounts/{id}/payments` (Credit Cards Phase 3, already built —
 * reused verbatim). Free-form amount only: no minimum-payment, full-payoff,
 * or installment-payoff presets, since no backing data exists for them
 * (spec: "Real Payment Flow"). */
export async function requestPayment(
  cardAccountId: string,
  body: CardPaymentRequestBody,
): Promise<CardPaymentAccepted> {
  const response = await authorizedFetch(
    `${gatewayOrigin()}/card-accounts/${encodeURIComponent(cardAccountId)}/payments`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as CardPaymentAccepted;
}
