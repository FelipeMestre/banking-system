import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Page } from "@/lib/api/types";
import type { Location } from "../types";

export async function getLocations(params: { limit: number; offset: number }): Promise<Page<Location>> {
  const query = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  const response = await authorizedFetch(`${gatewayOrigin()}/locations?${query}`);
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Page<Location>;
}
