import type { PurchaseStatus } from "../types";

/** Narrows an unknown JSON payload to a status event, since it came off the wire. */
export function parsePurchaseStatus(payload: unknown): PurchaseStatus | null {
  if (typeof payload !== "object" || payload === null) return null;
  const candidate = payload as Record<string, unknown>;
  const { request_id: requestId, status } = candidate;
  if (typeof requestId !== "string") return null;
  if (status !== "pending" && status !== "approved" && status !== "declined") return null;
  return {
    request_id: requestId,
    status,
    reason: typeof candidate.reason === "string" ? candidate.reason : undefined,
    ts: typeof candidate.ts === "string" ? candidate.ts : undefined,
  };
}
