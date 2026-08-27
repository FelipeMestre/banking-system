import { describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Location } from "../types";

export async function createLocation(body: { name: string }): Promise<Location> {
  const response = await fetch(`${gatewayOrigin()}/locations`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as Location;
}
