import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Location } from "../types";

/** Soft delete: the API sets active=false and returns the updated row. */
export async function deleteLocation(id: string): Promise<Location> {
  const response = await fetch(`${gatewayOrigin()}/locations/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as Location;
}
