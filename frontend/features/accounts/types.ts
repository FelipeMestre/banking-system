/** An account resource, as returned by GET /accounts. */
export interface Account {
  id: string;
  account_number: string;
  currency: string;
  customer_id: string;
  branch_id: string;
  /** Integer cents. Read-only — eventually consistent with the ledger. */
  balance: number;
  status: "active" | "blocked" | "closed";
}

/** The home page's account summary: the wire `Account` plus a display label
 * the backend has no column for (no `name`/nickname on `accounts` today). */
export type AccountSummary = Account & { label: string };

/** KYC fields required only when auto-linking a never-before-seen Auth0
 * identity via `POST /accounts/me` (amendment — `gender` stays optional). */
export interface FirstAccountKyc {
  identification_number: string;
  first_name: string;
  last_name: string;
  /** `YYYY-MM-DD`. */
  date_of_birth: string;
  gender?: string;
}
