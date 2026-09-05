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
