/** Wire types for the gateway API (spec §4, §6). All amounts are integer cents. */

/** The v2 account resource shown on the home page. */
export interface Account {
  id: string;
  account_number: string;
  currency: string;
  customer_id: string;
  branch_id: string;
  balance: number;
  status: "active" | "blocked" | "closed";
}

/**
 * A cleared movement on an account, shown on the home page's transactions
 * table. No endpoint returns this yet — movements live in the `account-events`
 * topic, and a read model would need to project them the same way
 * `accounts.balance` is projected. Amounts stay integer cents here, matching
 * the wire-amounts convention everywhere else; formatting happens at render.
 */
export interface Transaction {
  id: string;
  /** ISO 8601 date; formatted for display where it's rendered. */
  date: string;
  description: string;
  reference: string;
  /** 0 when this row is a debit. */
  creditCents: number;
  /** 0 when this row is a credit. */
  debitCents: number;
  /** The account's balance immediately after this movement. */
  balanceCents: number;
}

export interface TransferRequestBody {
  source_account: string;
  destination_account: string;
  amount: number;
}

/** 202 Accepted from POST /transfer. */
export interface TransferAccepted {
  request_id: string;
  status: "pending";
  fee_amount: number;
}

/** A verdict from the ledger, via the WebSocket or GET .../status. */
export interface TransferStatus {
  request_id: string;
  status: "pending" | "approved" | "declined";
  account_id?: string;
  reason?: string;
  ts?: string;
}

/** What the UI is currently showing for a single transfer attempt. */
export type Phase =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "pending"; requestId: string; feeAmount: number; amount: number }
  | { kind: "approved"; requestId: string; status: TransferStatus }
  | { kind: "declined"; requestId: string; status: TransferStatus }
  /** The gateway stopped waiting before the ledger answered. */
  | { kind: "unresolved"; requestId: string }
  | { kind: "error"; message: string };
