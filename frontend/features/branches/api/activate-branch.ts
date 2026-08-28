import { updateBranch } from "./update-branch";
import type { Branch } from "../types";

export function activateBranch(id: string): Promise<Branch> {
  return updateBranch(id, { active: true });
}
