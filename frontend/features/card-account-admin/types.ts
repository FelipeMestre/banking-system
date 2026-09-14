/**
 * Wire types for the admin Credit Cards tab (`card-account-admin`).
 *
 * Deliberately separate from `features/credit-cards/types.ts`: that module
 * covers the customer-facing read/pay surface, this one covers admin
 * mutations (issue/limit/status/renew/block). `CardAccount` and `MaskedCard`
 * themselves are reused via import from `credit-cards/types` rather than
 * redefined here, per the architecture note in the task spec.
 */

/** Mirrors `CardAccountCreateDTO` (openbankapi/api/v1/dtos/card_account_dto.py). */
export interface IssueCardAccountRequest {
  customer_id: string;
  paying_account_id: string;
  /** Decimal-as-string, > 0. */
  credit_limit: string;
  reason?: string;
}

/** Mirrors `CardIssuedDTO` — unmasked `card_number`, only ever returned right
 * after issue or renew, never listed. */
export interface CardIssued {
  id: string;
  card_account_id: string;
  card_number: string;
  expiration_date: string;
  status: "active" | "blocked" | "replaced" | "expired";
}

/** Mirrors the `POST /card-accounts` 201 response body. */
export interface IssueCardAccountResponse {
  card_account: import("../credit-cards/types").CardAccount;
  card: CardIssued;
}

/** Mirrors `CardAccountUpdateDTO` (`PUT /card-accounts/{id}`). */
export interface UpdateCreditLimitRequest {
  credit_limit?: string;
  reason?: string;
}

/** Mirrors `CardAccountStatusUpdateDTO` (`POST /card-accounts/{id}/status`). */
export interface UpdateCardAccountStatusRequest {
  status: "active" | "blocked" | "closed";
  reason?: string;
}

/** Mirrors `CardAccountRenewDTO` (`POST /card-accounts/{id}/cards`) — every
 * field optional, `{}` is a valid body. */
export interface RenewCardRequest {
  reason?: string;
}

/** Mirrors the card-status update body (`POST /cards/{card_number}/status`).
 * Only `active`/`blocked` are ever offered from the UI — `replaced`/`expired`
 * are system-only transitions the backend rejects with 409. */
export interface UpdateCardStatusRequest {
  status: "active" | "blocked";
  reason?: string;
}
