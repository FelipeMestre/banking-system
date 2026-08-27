import { updateLocation } from "./update-location";
import type { Location } from "../types";

/** Reactivates a soft-deleted location. Same PUT the edit form uses, just fixed to active=true. */
export async function activateLocation(id: string): Promise<Location> {
  return updateLocation(id, { active: true });
}
