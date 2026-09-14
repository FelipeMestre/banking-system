import type { AppliedRate } from "@/lib/api/types";

export type { AppliedRate } from "@/lib/api/types";

/** Wire shape for `POST /admin/deposits` (spec: admin-cash-deposits). */
export interface DepositRequestBody {
  account_number: string;
  /** Integer cents, > 0. */
  amount: number;
  /** One of EUR, GBP, USD (uppercase). */
  currency: string;
  reason?: string;
}

/** Wire shape returned by `POST /admin/deposits`. */
export interface DepositResponse {
  request_id: string;
  approved: boolean;
  /** Integer cents credited to the account, in the account's own currency. */
  amount_applied: number;
  applied_rate?: AppliedRate;
  /** Integer cents, the account's balance after the deposit. */
  new_balance: number;
}
