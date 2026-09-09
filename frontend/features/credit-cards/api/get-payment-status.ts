import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import { parsePaymentStatus } from "./parse-payment-status";
import type { CardPaymentStatus } from "../types";

/** `GET /payments/{request_id}/status` (Credit Cards Phase 3). */
export async function getPaymentStatus(requestId: string): Promise<CardPaymentStatus> {
  const response = await fetch(`${gatewayOrigin()}/payments/${encodeURIComponent(requestId)}/status`);
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  const parsed = parsePaymentStatus(await response.json());
  if (parsed === null) {
    throw new Error("The gateway returned a status this client does not understand.");
  }
  return parsed;
}
