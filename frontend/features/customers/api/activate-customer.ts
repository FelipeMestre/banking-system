import { updateCustomer } from "./update-customer";
import type { Customer } from "../types";

export function activateCustomer(id: string): Promise<Customer> {
  return updateCustomer(id, { active: true });
}
