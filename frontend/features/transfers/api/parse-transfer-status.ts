import type { TransferStatus } from "../types";

/** Narrows an unknown JSON payload to a status event, since it came off the wire. */
export function parseTransferStatus(payload: unknown): TransferStatus | null {
  if (typeof payload !== "object" || payload === null) return null;
  const candidate = payload as Record<string, unknown>;
  const { request_id: requestId, status } = candidate;
  if (typeof requestId !== "string") return null;
  if (status !== "pending" && status !== "approved" && status !== "declined") return null;
  return {
    request_id: requestId,
    status,
    account_id: typeof candidate.account_id === "string" ? candidate.account_id : undefined,
    reason: typeof candidate.reason === "string" ? candidate.reason : undefined,
    ts: typeof candidate.ts === "string" ? candidate.ts : undefined,
  };
}
