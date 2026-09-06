import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Page } from "@/lib/api/types";
import type { CardMovement } from "../types";

/** `GET /card-accounts/{id}/movements`, paginated newest-first. Passing
 * `statementId` scopes the list to one billing cycle: a single-charge
 * purchase matches by date falling inside that statement's period, while a
 * billed installment matches by the statement it was actually billed onto
 * (`credit-card-monthly-batch-statements`). */
export async function getMovements(params: {
  cardAccountId: string;
  limit: number;
  offset: number;
  statementId?: string;
}): Promise<Page<CardMovement>> {
  const query = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  if (params.statementId) {
    query.set("statement_id", params.statementId);
  }
  const response = await authorizedFetch(
    `${gatewayOrigin()}/card-accounts/${encodeURIComponent(params.cardAccountId)}/movements?${query}`,
  );
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Page<CardMovement>;
}
