/**
 * Wire types for the customer-facing Cards page (`credit-cards-frontend-page`).
 *
 * Deliberately separate from `features/cards/types.ts` (the admin-only
 * purchase-simulation module): that module's `CardListItem` is an unmasked
 * admin listing row from a different endpoint (`GET /cards`) and must never
 * be imported here (spec: "Module boundary is respected").
 *
 * `credit_limit`/`used_credit_estimate`/amount-like fields are `Decimal` on
 * the backend, serialized as JSON strings (e.g. `"120.00"`) — unlike
 * `features/accounts`' integer-cents `balance`, these arrive as decimal
 * strings and must be parsed for display, never treated as cents.
 */

/** Mirrors `CardAccountResponseDTO` (openbankapi/api/v1/dtos/card_account_dto.py). */
export interface CardAccount {
  id: string;
  customer_id: string;
  paying_account_id: string;
  credit_limit: string;
  status: "active" | "blocked" | "closed";
  used_credit: number;
}

/** Mirrors `CardMaskedDTO` (openbankapi/api/v1/dtos/card_dto.py) — the masking
 * is already applied server-side via `mask_card_number`. */
export interface MaskedCard {
  id: string;
  card_account_id: string;
  card_number: string;
  expiration_date: string;
  status: "active" | "blocked" | "replaced" | "expired";
}

/** One row from `GET /card-accounts?customer_id=` — `card` is null only if
 * the account somehow has no active card (never true for a freshly issued
 * account, but the backend types it as optional). */
export interface CardAccountListItem {
  card_account: CardAccount;
  card: MaskedCard | null;
}

/** Mirrors `UsedCreditEstimateDTO` (openbankapi/api/v1/dtos/card_usage_dto.py).
 * `is_estimate` is always true — this is a derived approximation from
 * `card_movements`, never the Flink Card Service's authoritative state. */
export interface UsedCreditEstimate {
  card_account_id: string;
  used_credit_estimate: string;
  credit_limit: string;
  currency: string;
  is_estimate: boolean;
  movement_count: number;
}

/** Mirrors `CardMovementDTO` (openbankapi/api/v1/dtos/card_usage_dto.py). */
export interface CardMovement {
  id: string;
  movement_type: "purchase" | "payment" | "fee" | "interest" | "refund" | "declined";
  amount: string;
  currency: string;
  occurred_at: string;
  description?: string | null;
  decline_reason?: string | null;
  fx_pair?: string | null;
  fx_applied_rate?: string | null;
  installment_count?: number | null;
  installment_amount?: string | null;
}

/** Mirrors `CardPaymentRequestDTO` — `amount` is integer cents in the paying
 * account's own currency (resolved server-side, never sent by the client). */
export interface CardPaymentRequestBody {
  amount: number;
  source_account: string;
}

/** Mirrors `CardPaymentAcceptedDTO`. */
export interface CardPaymentAccepted {
  request_id: string;
  status: string;
}

/** Mirrors `CardPaymentStatusDTO`, off `GET/WS /payments/{request_id}/status`. */
export interface CardPaymentStatus {
  request_id: string;
  status: "pending" | "approved" | "declined";
  reason?: string;
  ts?: string;
}

/**
 * Mirrors `StatementDTO` (openbankapi/api/v1/dtos/statement_dto.py) — one
 * closed billing cycle. `status` is the raw backend enum
 * (`closed`/`paid`/`overdue`); the frontend derives its own display label
 * from `status` + `paid_in_full` + `paid_by_due_date` rather than trusting
 * any single field alone (see `deriveStatementStatusLabel`), since an
 * `overdue` statement that later gets fully paid still carries
 * `paid_by_due_date: false` forever.
 */
export interface Statement {
  id: string;
  card_account_id: string;
  period_start: string;
  period_end: string;
  due_date: string;
  purchases_total: string;
  interest_total: string;
  total_due: string;
  paid_amount: string;
  credit_balance: string;
  late_fees_total: string;
  minimum_payment: string;
  paid_in_full: boolean;
  paid_by_due_date: boolean;
  status: "open" | "closed" | "paid" | "overdue";
  created_at: string;
  updated_at: string;
}

/** Mirrors `InstallmentPayoffDTO` — the "settle all installment balances
 * early" figure, safe to expose verbatim since installments carry 0% interest. */
export interface InstallmentPayoff {
  card_account_id: string;
  payoff_amount: string;
  currency: string;
}
