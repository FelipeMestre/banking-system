import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Branch } from "../types";

export interface UpdateBranchBody {
  code?: string;
  name?: string;
  location_id?: string;
  active?: boolean;
}

export async function updateBranch(id: string, body: UpdateBranchBody): Promise<Branch> {
  const response = await authorizedFetch(`${gatewayOrigin()}/branches/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Branch;
}
