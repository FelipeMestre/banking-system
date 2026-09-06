import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TransactionsList } from "@/features/transactions/components/TransactionsList";
import type { Transaction } from "@/features/transactions/types";

describe("TransactionsList", () => {
  it("renders a deposit row with its own type label, not blank", () => {
    const deposit: Transaction = {
      id: "t1", request_id: "r1", type: "deposit", amount: 250000,
      counterparty_account: null, decline_reason: null, ts: "2026-09-04T00:00:00Z",
    };

    render(<TransactionsList transactions={[deposit]} currencyCode="USD" />);

    expect(screen.getByText("Deposit")).toBeInTheDocument();
  });

  it("shows a placeholder, not a blank cell, when a deposit has no counterparty", () => {
    const deposit: Transaction = {
      id: "t1", request_id: "r1", type: "deposit", amount: 250000,
      counterparty_account: null, decline_reason: null, ts: "2026-09-04T00:00:00Z",
    };

    render(<TransactionsList transactions={[deposit]} currencyCode="USD" />);

    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("still renders every other known transaction type", () => {
    const rows: Transaction[] = [
      { id: "t1", request_id: "r1", type: "debit", amount: 100, counterparty_account: "1", decline_reason: null, ts: "2026-09-04T00:00:00Z" },
      { id: "t2", request_id: "r2", type: "credit", amount: 100, counterparty_account: "1", decline_reason: null, ts: "2026-09-04T00:00:00Z" },
      { id: "t3", request_id: "r3", type: "declined", amount: 100, counterparty_account: "1", decline_reason: "insufficient_funds", ts: "2026-09-04T00:00:00Z" },
    ];

    render(<TransactionsList transactions={rows} currencyCode="USD" />);

    expect(screen.getByText("Debit")).toBeInTheDocument();
    expect(screen.getByText("Credit")).toBeInTheDocument();
    expect(screen.getByText("Declined")).toBeInTheDocument();
  });
});
