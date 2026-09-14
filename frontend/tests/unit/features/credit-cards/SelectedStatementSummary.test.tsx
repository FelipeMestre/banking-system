import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SelectedStatementSummary } from "@/features/credit-cards/components/SelectedStatementSummary";
import type { Statement } from "@/features/credit-cards/types";

function makeStatement(overrides: Partial<Statement>): Statement {
  return {
    id: "st-1", card_account_id: "ca-1", period_start: "2026-07-20", period_end: "2026-08-20",
    due_date: "2026-09-10", purchases_total: "100.00", interest_total: "0.00", total_due: "120.00",
    paid_amount: "0.00", credit_balance: "0.00", late_fees_total: "0.00", minimum_payment: "15.00",
    paid_in_full: false, paid_by_due_date: false, status: "closed",
    created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z", payable: true,
    ...overrides,
  };
}

describe("SelectedStatementSummary", () => {
  it("shows total due, minimum payment, closing date, and due date", () => {
    render(
      <SelectedStatementSummary
        statement={makeStatement({})}
        onDownload={vi.fn()}
        downloading={false}
        onPay={vi.fn()}
      />,
    );

    expect(screen.getByText("$120.00")).toBeInTheDocument();
    expect(screen.getByText("$15.00")).toBeInTheDocument();
    expect(screen.getByText("Aug 20, 2026")).toBeInTheDocument();
    expect(screen.getByText("Sep 10, 2026")).toBeInTheDocument();
  });

  it("shows the credit-balance banner only when credit_balance is positive", () => {
    const { rerender } = render(
      <SelectedStatementSummary
        statement={makeStatement({ credit_balance: "0.00" })}
        onDownload={vi.fn()}
        downloading={false}
        onPay={vi.fn()}
      />,
    );
    expect(screen.queryByText("Credit balance")).not.toBeInTheDocument();

    rerender(
      <SelectedStatementSummary
        statement={makeStatement({ credit_balance: "25.00" })}
        onDownload={vi.fn()}
        downloading={false}
        onPay={vi.fn()}
      />,
    );
    expect(screen.getByText("Credit balance")).toBeInTheDocument();
  });

  it("calls onDownload", () => {
    const onDownload = vi.fn();
    render(
      <SelectedStatementSummary
        statement={makeStatement({})}
        onDownload={onDownload}
        downloading={false}
        onPay={vi.fn()}
      />,
    );

    screen.getByRole("button", { name: "Download current statement" }).click();

    expect(onDownload).toHaveBeenCalledOnce();
  });

  it("calls onPay", () => {
    const onPay = vi.fn();
    render(
      <SelectedStatementSummary
        statement={makeStatement({})}
        onDownload={vi.fn()}
        downloading={false}
        onPay={onPay}
      />,
    );

    screen.getByRole("button", { name: "Pay" }).click();

    expect(onPay).toHaveBeenCalledOnce();
  });

  it("omits the Pay affordance entirely when onPay is not provided (non-payable, history-only statement)", () => {
    render(
      <SelectedStatementSummary
        statement={makeStatement({ payable: false })}
        onDownload={vi.fn()}
        downloading={false}
      />,
    );

    expect(screen.queryByRole("button", { name: "Pay" })).not.toBeInTheDocument();
  });

  it("disables the download button and shows a preparing label while downloading", () => {
    render(
      <SelectedStatementSummary
        statement={makeStatement({})}
        onDownload={vi.fn()}
        downloading={true}
        onPay={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: "Preparing…" });
    expect(button).toBeDisabled();
  });
});
