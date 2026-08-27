import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Page } from "@/lib/api/types";
import type { Branch } from "../types";

export async function getBranches(params: { limit: number; offset: number }): Promise<Page<Branch>> {
  const query = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  const response = await fetch(`${gatewayOrigin()}/branches?${query}`);
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as Page<Branch>;
}
