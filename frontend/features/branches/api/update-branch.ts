import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Branch } from "../types";

export interface UpdateBranchBody {
  code?: string;
  name?: string;
  location_id?: string;
  active?: boolean;
}

export async function updateBranch(id: string, body: UpdateBranchBody): Promise<Branch> {
  const response = await fetch(`${gatewayOrigin()}/branches/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as Branch;
}
