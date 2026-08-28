import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Branch } from "../types";

export interface CreateBranchBody {
  code: string;
  name: string;
  location_id: string;
}

export async function createBranch(body: CreateBranchBody): Promise<Branch> {
  const response = await fetch(`${gatewayOrigin()}/branches`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as Branch;
}
