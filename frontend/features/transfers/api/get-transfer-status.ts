import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import { parseTransferStatus } from "./parse-transfer-status";
import type { TransferStatus } from "../types";

export async function getTransferStatus(requestId: string): Promise<TransferStatus> {
  const response = await fetch(
    `${gatewayOrigin()}/transfer/${encodeURIComponent(requestId)}/status`,
  );
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  const parsed = parseTransferStatus(await response.json());
  if (parsed === null) {
    throw new Error("The gateway returned a status this client does not understand.");
  }
  return parsed;
}
