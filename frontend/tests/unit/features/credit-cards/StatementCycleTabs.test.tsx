import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StatementCycleTabs } from "@/features/credit-cards/components/StatementCycleTabs";
import type { Statement } from "@/features/credit-cards/types";

function makeStatement(overrides: Partial<Statement>): Statement {
  return {
    id: "st-1", card_account_id: "ca-1", period_start: "2026-07-20", period_end: "2026-08-20",
    due_date: "2026-09-10", purchases_total: "100.00", interest_total: "0.00", total_due: "100.00",
    paid_amount: "0.00", credit_balance: "0.00", late_fees_total: "0.00", minimum_payment: "10.00",
    paid_in_full: false, paid_by_due_date: false, status: "closed",
    created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z",
    ...overrides,
  };
}

describe("StatementCycleTabs", () => {
  it("shows an empty message when there are no closed cycles yet", () => {
    render(<StatementCycleTabs statements={[]} selectedStatementId={null} onSelect={vi.fn()} />);
    expect(screen.getByText("No closed billing cycles yet.")).toBeInTheDocument();
  });

  it("renders one tab per statement with its derived status label", () => {
    const statements = [
      makeStatement({ id: "st-1", period_end: "2026-08-20", status: "paid", paid_in_full: true, paid_by_due_date: true }),
      makeStatement({ id: "st-2", period_end: "2026-07-20", status: "overdue", paid_in_full: false, paid_by_due_date: false }),
    ];

    render(<StatementCycleTabs statements={statements} selectedStatementId="st-1" onSelect={vi.fn()} />);

    expect(screen.getByText("2026-08-20")).toBeInTheDocument();
    expect(screen.getByText("2026-07-20")).toBeInTheDocument();
    expect(screen.getByText("Paid in full")).toBeInTheDocument();
    expect(screen.getByText("Missed minimum, late fee applied")).toBeInTheDocument();
  });

  it("calls onSelect with the clicked statement id", () => {
    const onSelect = vi.fn();
    const statements = [makeStatement({ id: "st-1" }), makeStatement({ id: "st-2", period_end: "2026-07-20" })];
    render(<StatementCycleTabs statements={statements} selectedStatementId="st-1" onSelect={onSelect} />);

    // Radix's Tabs.Trigger activates on `mousedown` (and on focus, for
    // automatic activation mode) rather than `click` — `fireEvent.click`
    // alone never fires a `mousedown` in jsdom.
    fireEvent.mouseDown(screen.getByRole("tab", { name: /2026-07-20/ }));

    expect(onSelect).toHaveBeenCalledWith("st-2");
  });
});
