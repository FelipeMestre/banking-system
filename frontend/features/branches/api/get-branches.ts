import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Page } from "@/lib/api/types";
import type { Branch } from "../types";

export async function getBranches(params: { limit: number; offset: number }): Promise<Page<Branch>> {
  const query = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  const response = await authorizedFetch(`${gatewayOrigin()}/branches?${query}`);
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Page<Branch>;
}
