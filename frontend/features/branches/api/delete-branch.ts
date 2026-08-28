import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Branch } from "../types";

export async function deleteBranch(id: string): Promise<Branch> {
  const response = await fetch(`${gatewayOrigin()}/branches/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as Branch;
}
