import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Page } from "@/lib/api/types";
import type { CardAccountListItem } from "../types";

/** `GET /card-accounts?customer_id=&status=` (Credit Cards Phase 1; `status`
 * filter added by the admin-panel change — combinable with pagination,
 * omitted entirely when not provided rather than sent empty). */
export async function getCardAccounts(params: {
  customerId: string;
  limit: number;
  offset: number;
  status?: "active" | "blocked" | "closed";
}): Promise<Page<CardAccountListItem>> {
  const query = new URLSearchParams({
    customer_id: params.customerId,
    limit: String(params.limit),
    offset: String(params.offset),
  });
  if (params.status) {
    query.set("status", params.status);
  }
  const response = await authorizedFetch(`${gatewayOrigin()}/card-accounts?${query}`);
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Page<CardAccountListItem>;
}
