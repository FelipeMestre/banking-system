import type { AppliedRate } from "@/lib/api/types";

export type { AppliedRate } from "@/lib/api/types";

/** Wire shape for `POST /admin/withdrawals` (mirrors admin-cash-deposits). */
export interface WithdrawalRequestBody {
  account_number: string;
  /** Integer cents, > 0. */
  amount: number;
  /** One of EUR, GBP, USD (uppercase). */
  currency: string;
  reason?: string;
}

/** Wire shape returned by `POST /admin/withdrawals`. Unlike a deposit, a
 * withdrawal can be declined (e.g. insufficient funds) — that's a normal,
 * resolved business outcome carried as `approved: false`, not an HTTP error,
 * so the `amount_applied`/`applied_rate`/`new_balance` fields are only
 * present when `approved` is `true`, and `reason` only when it's `false`. */
export interface WithdrawalResponse {
  request_id: string;
  approved: boolean;
  /** Integer cents debited, in the account's own currency. Present only when approved. */
  amount_applied?: number;
  applied_rate?: AppliedRate;
  /** Integer cents, the account's balance after the withdrawal. Present only when approved. */
  new_balance?: number;
  /** Present only when NOT approved, e.g. "insufficient_funds" or "invalid_amount". */
  reason?: string;
}
