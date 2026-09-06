import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatementTotalsSidebar } from "@/features/credit-cards/components/StatementTotalsSidebar";
import type { CardMovement, Statement } from "@/features/credit-cards/types";

const STATEMENT: Statement = {
  id: "st-1", card_account_id: "ca-1", period_start: "2026-07-20", period_end: "2026-08-20",
  due_date: "2026-09-10", purchases_total: "850.00", interest_total: "12.50", total_due: "887.50",
  paid_amount: "0.00", credit_balance: "0.00", late_fees_total: "25.00", minimum_payment: "40.00",
  paid_in_full: false, paid_by_due_date: false, status: "closed",
  created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z",
};

function movement(overrides: Partial<CardMovement>): CardMovement {
  return {
    id: "m-1", movement_type: "purchase", amount: "10.00", currency: "USD",
    occurred_at: "2026-08-01T00:00:00Z", ...overrides,
  };
}

describe("StatementTotalsSidebar", () => {
  it("shows the statement's own stored totals verbatim, not re-summed from movements", () => {
    render(<StatementTotalsSidebar statement={STATEMENT} cycleMovements={[]} />);

    expect(screen.getByText("$850.00")).toBeInTheDocument();
    expect(screen.getByText("$12.50")).toBeInTheDocument();
    expect(screen.getByText("$25.00")).toBeInTheDocument();
  });

  it("sums total payments made from the cycle-scoped movements", () => {
    const movements = [
      movement({ id: "m-1", movement_type: "payment", amount: "40.00" }),
      movement({ id: "m-2", movement_type: "payment", amount: "10.00" }),
      movement({ id: "m-3", movement_type: "purchase", amount: "999.00" }),
    ];

    render(<StatementTotalsSidebar statement={STATEMENT} cycleMovements={movements} />);

    expect(screen.getByText("$50.00")).toBeInTheDocument();
  });
});
