import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { CurrentCycleProjection } from "../types";

/** `GET /card-accounts/{id}/current-cycle` — the live, never-persisted
 * projection of the still-open billing cycle. Computed fresh on every call;
 * never cached or memoized on this side either. */
export async function getCurrentCycle(params: {
  cardAccountId: string;
}): Promise<CurrentCycleProjection> {
  const response = await authorizedFetch(
    `${gatewayOrigin()}/card-accounts/${encodeURIComponent(params.cardAccountId)}/current-cycle`,
  );
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as CurrentCycleProjection;
}
