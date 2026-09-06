import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Page } from "@/lib/api/types";
import type { CardMovement } from "../types";

/** `GET /card-accounts/{id}/movements`, paginated newest-first. */
export async function getMovements(params: {
  cardAccountId: string;
  limit: number;
  offset: number;
}): Promise<Page<CardMovement>> {
  const query = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  const response = await authorizedFetch(
    `${gatewayOrigin()}/card-accounts/${encodeURIComponent(params.cardAccountId)}/movements?${query}`,
  );
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Page<CardMovement>;
}
