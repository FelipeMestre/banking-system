import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { MaskedCard } from "@/features/credit-cards/types";
import type { UpdateCardStatusRequest } from "../types";

/** `POST /cards/{card_number}/status` — block/unblock the physical card,
 * independent of the account. Uses the card's real `card_number` as the URL
 * path param (masking is display-only — the DTO's `card_number` field is
 * still the real value used for routing). Only `active`/`blocked` are ever
 * sent; `replaced`/`expired` are system-only transitions the backend 409s. */
export async function updateCardStatus(
  cardNumber: string,
  body: UpdateCardStatusRequest,
): Promise<MaskedCard> {
  const response = await authorizedFetch(
    `${gatewayOrigin()}/cards/${encodeURIComponent(cardNumber)}/status`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as MaskedCard;
}
