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
