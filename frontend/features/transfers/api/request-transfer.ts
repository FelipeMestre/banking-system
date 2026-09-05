import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { TransferAccepted, TransferRequestBody } from "../types";

export async function requestTransfer(body: TransferRequestBody): Promise<TransferAccepted> {
  const response = await authorizedFetch(`${gatewayOrigin()}/transfer`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as TransferAccepted;
}
