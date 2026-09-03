/** Wire types for the gateway's transfer endpoints (spec §4, §6). All amounts are integer cents. */

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

/** A recipient looked up by account number via GET /accounts/{n} + GET /customers/{id}. */
export interface RecipientPreview {
  account_number: string;
  currency: string;
  name: string;
  initials: string;
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
