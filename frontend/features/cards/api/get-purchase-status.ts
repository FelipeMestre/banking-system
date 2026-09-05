import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import { parsePurchaseStatus } from "./parse-purchase-status";
import type { PurchaseStatus } from "../types";

/** `GET /purchases/{request_id}/status` (Credit Cards Phase 2). */
export async function getPurchaseStatus(requestId: string): Promise<PurchaseStatus> {
  const response = await fetch(
    `${gatewayOrigin()}/purchases/${encodeURIComponent(requestId)}/status`,
  );
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  const parsed = parsePurchaseStatus(await response.json());
  if (parsed === null) {
    throw new Error("The gateway returned a status this client does not understand.");
  }
  return parsed;
}
