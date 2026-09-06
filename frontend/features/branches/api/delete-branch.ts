import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Branch } from "../types";

export async function deleteBranch(id: string): Promise<Branch> {
  const response = await authorizedFetch(`${gatewayOrigin()}/branches/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Branch;
}
