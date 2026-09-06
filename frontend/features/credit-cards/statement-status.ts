import type { Statement } from "./types";

export type StatementStatusLabel =
  | "Still open"
  | "Paid in full"
  | "Paid minimum, not full"
  | "Missed minimum, late fee applied";

/**
 * Derives the customer-facing status label from `status` +
 * `paid_in_full`/`paid_by_due_date` — never from `status` alone.
 * `run_due_date_check` (openbankapi/domain/service/statement_service.py)
 * finalizes a statement exactly once: while it is still `closed`, nothing
 * has been decided yet, so it reads as "still open" even though the backend
 * enum literally says "closed". Once finalized it moves to `paid` (full) or
 * `overdue` — and `overdue` still splits into "paid the minimum, just not in
 * full" vs. "missed the minimum entirely" using `paid_by_due_date`, since a
 * late fee is only ever applied in the second case.
 */
export function deriveStatementStatusLabel(statement: Statement): StatementStatusLabel {
  if (statement.status === "paid") {
    return "Paid in full";
  }
  if (statement.status === "overdue") {
    return statement.paid_by_due_date ? "Paid minimum, not full" : "Missed minimum, late fee applied";
  }
  // `closed` (not yet finalized) and the legacy `open` value both read the
  // same way to a customer: nothing has been decided about this cycle yet.
  return "Still open";
}

export function statementStatusBadgeVariant(
  label: StatementStatusLabel,
): "default" | "secondary" | "destructive" {
  switch (label) {
    case "Paid in full":
      return "default";
    case "Missed minimum, late fee applied":
      return "destructive";
    default:
      return "secondary";
  }
}
