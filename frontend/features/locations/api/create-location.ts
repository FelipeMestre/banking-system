import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Location } from "../types";

export async function createLocation(body: { name: string }): Promise<Location> {
  const response = await authorizedFetch(`${gatewayOrigin()}/locations`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as Location;
}
