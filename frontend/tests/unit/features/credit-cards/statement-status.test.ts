import { describe, expect, it } from "vitest";
import { deriveStatementStatusLabel, statementStatusBadgeVariant } from "@/features/credit-cards/statement-status";
import type { Statement } from "@/features/credit-cards/types";

function makeStatement(overrides: Partial<Statement>): Statement {
  return {
    id: "st-1", card_account_id: "ca-1", period_start: "2026-07-20", period_end: "2026-08-20",
    due_date: "2026-09-10", purchases_total: "100.00", interest_total: "0.00", total_due: "100.00",
    paid_amount: "0.00", credit_balance: "0.00", late_fees_total: "0.00", minimum_payment: "10.00",
    paid_in_full: false, paid_by_due_date: false, status: "closed",
    created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z", payable: true,
    ...overrides,
  };
}

describe("deriveStatementStatusLabel", () => {
  it("reads a not-yet-finalized (closed) statement as still open", () => {
    const statement = makeStatement({ status: "closed", paid_in_full: false, paid_by_due_date: false });
    expect(deriveStatementStatusLabel(statement)).toBe("Still open");
  });

  it("reads a finalized paid statement as paid in full", () => {
    const statement = makeStatement({ status: "paid", paid_in_full: true, paid_by_due_date: true });
    expect(deriveStatementStatusLabel(statement)).toBe("Paid in full");
  });

  it("reads an overdue statement that paid the minimum as paid minimum, not full", () => {
    const statement = makeStatement({ status: "overdue", paid_in_full: false, paid_by_due_date: true });
    expect(deriveStatementStatusLabel(statement)).toBe("Paid minimum, not full");
  });

  it("reads an overdue statement that missed the minimum as missed minimum, late fee applied", () => {
    const statement = makeStatement({ status: "overdue", paid_in_full: false, paid_by_due_date: false });
    expect(deriveStatementStatusLabel(statement)).toBe("Missed minimum, late fee applied");
  });
});

describe("statementStatusBadgeVariant", () => {
  it("maps paid in full to default, missed minimum to destructive, and everything else to secondary", () => {
    expect(statementStatusBadgeVariant("Paid in full")).toBe("default");
    expect(statementStatusBadgeVariant("Missed minimum, late fee applied")).toBe("destructive");
    expect(statementStatusBadgeVariant("Still open")).toBe("secondary");
    expect(statementStatusBadgeVariant("Paid minimum, not full")).toBe("secondary");
  });
});
