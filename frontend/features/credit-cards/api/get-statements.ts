import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Statement } from "../types";

/** `GET /card-accounts/{id}/statements` — every closed billing cycle for
 * this account, newest `period_end` first. Powers the billing-cycle tab
 * strip (`credit-card-monthly-batch-statements`). */
export async function getStatements(params: {
  cardAccountId: string;
  limit?: number;
}): Promise<Statement[]> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) {
    query.set("limit", String(params.limit));
  }
  const suffix = query.toString() ? `?${query}` : "";
  const response = await authorizedFetch(
    `${gatewayOrigin()}/card-accounts/${encodeURIComponent(params.cardAccountId)}/statements${suffix}`,
  );
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Statement[];
}
