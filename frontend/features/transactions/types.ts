/** A row of the transactions read model, as returned by
 * `GET /accounts/{account_number}/transactions` (spec §3.3). */
export interface Transaction {
  id: string;
  request_id: string;
  type: "debit" | "credit" | "declined";
  /** Integer cents. */
  amount: number;
  counterparty_account: string;
  decline_reason: string | null;
  /** ISO 8601 timestamp. */
  ts: string;
}

/** Keyset-paginated, not limit/offset: `next_cursor` is opaque — pass it
 * back unmodified for the next page, and stop once it is `null`. */
export interface TransactionsPage {
  items: Transaction[];
  next_cursor: string | null;
}
