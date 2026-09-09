import type { CardPaymentStatus } from "../types";

/** Narrows an unknown JSON payload to a card-payment status event, mirroring
 * `features/cards/api/parse-purchase-status.ts` exactly. */
export function parsePaymentStatus(payload: unknown): CardPaymentStatus | null {
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
