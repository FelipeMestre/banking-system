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
    created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z", payable: true,
    ...overrides,
  };
}

describe("StatementCycleTabs", () => {
  it("shows an empty message alongside the current-cycle tab when there are no closed cycles yet", () => {
    render(
      <StatementCycleTabs
        statements={[]}
        selectedStatementId={null}
        onSelect={vi.fn()}
        onDownload={vi.fn()}
        downloading={false}
      />,
    );
    expect(screen.getByText("Current cycle")).toBeInTheDocument();
    expect(screen.getByText("No closed billing cycles yet.")).toBeInTheDocument();
  });

  it("renders one tab per statement with its derived status label", () => {
    const statements = [
      makeStatement({ id: "st-1", period_end: "2026-08-20", status: "paid", paid_in_full: true, paid_by_due_date: true }),
      makeStatement({ id: "st-2", period_end: "2026-07-20", status: "overdue", paid_in_full: false, paid_by_due_date: false }),
    ];

    render(
      <StatementCycleTabs
        statements={statements}
        selectedStatementId="st-1"
        onSelect={vi.fn()}
        onDownload={vi.fn()}
        downloading={false}
      />,
    );

    expect(screen.getByText("AUG 2026")).toBeInTheDocument();
    expect(screen.getByText("JUL 2026")).toBeInTheDocument();
    expect(screen.getByText("Paid in full")).toBeInTheDocument();
    expect(screen.getByText("Missed minimum — late fee applied")).toBeInTheDocument();
  });

  it("calls onSelect with the clicked statement id", () => {
    const onSelect = vi.fn();
    const statements = [makeStatement({ id: "st-1" }), makeStatement({ id: "st-2", period_end: "2026-07-20" })];
    render(
      <StatementCycleTabs
        statements={statements}
        selectedStatementId="st-1"
        onSelect={onSelect}
        onDownload={vi.fn()}
        downloading={false}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: /JUL 2026/ }));

    expect(onSelect).toHaveBeenCalledWith("st-2");
  });

  it("calls onSelect with null when the leading Current cycle tab is clicked", () => {
    const onSelect = vi.fn();
    const statements = [makeStatement({ id: "st-1" })];
    render(
      <StatementCycleTabs
        statements={statements}
        selectedStatementId="st-1"
        onSelect={onSelect}
        onDownload={vi.fn()}
        downloading={false}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: /Current cycle/ }));

    expect(onSelect).toHaveBeenCalledWith(null);
  });
});
