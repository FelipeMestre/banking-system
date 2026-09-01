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
