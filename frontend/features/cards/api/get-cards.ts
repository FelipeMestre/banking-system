import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Page } from "@/lib/api/types";
import type { CardListItem } from "../types";

/**
 * Every card across every customer (`GET /cards`, Credit Cards Phase 2 —
 * added specifically for the admin purchase-simulation picker; no other
 * client needs a cross-customer card list).
 */
export async function getCards(params: { limit: number; offset: number }): Promise<Page<CardListItem>> {
  const query = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  const response = await authorizedFetch(`${gatewayOrigin()}/cards?${query}`);
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Page<CardListItem>;
}
