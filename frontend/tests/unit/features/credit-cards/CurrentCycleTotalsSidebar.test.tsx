import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CurrentCycleTotalsSidebar } from "@/features/credit-cards/components/CurrentCycleTotalsSidebar";
import type { CardMovement } from "@/features/credit-cards/types";

function movement(overrides: Partial<CardMovement>): CardMovement {
  return {
    id: "m-1", movement_type: "purchase", amount: "10.00", currency: "USD",
    occurred_at: "2026-08-01T00:00:00Z", ...overrides,
  };
}

describe("CurrentCycleTotalsSidebar", () => {
  it("subtracts a payment made this cycle from 'Left to pay', unlike the projection's own Total to pay", () => {
    const movements = [
      movement({ id: "m-1", movement_type: "purchase", amount: "100.00" }),
      movement({ id: "m-2", movement_type: "payment", amount: "40.00" }),
    ];

    render(<CurrentCycleTotalsSidebar movements={movements} />);

    expect(screen.getByText("$100.00")).toBeInTheDocument();
    expect(screen.getByText("$40.00")).toBeInTheDocument();
    expect(screen.getByText("$60.00")).toBeInTheDocument();
  });

  it("floors Left to pay at zero when payments exceed purchases (overpayment)", () => {
    const movements = [
      movement({ id: "m-1", movement_type: "purchase", amount: "50.00" }),
      movement({ id: "m-2", movement_type: "payment", amount: "80.00" }),
    ];

    render(<CurrentCycleTotalsSidebar movements={movements} />);

    expect(screen.getByText("$0.00")).toBeInTheDocument();
  });

  it("includes the synthetic carried-balance and interest rows when overdue", () => {
    const movements = [
      movement({ id: "carried-balance", movement_type: "carried_balance", amount: "200.00" }),
      movement({ id: "carried-balance-interest", movement_type: "interest", amount: "5.00" }),
      movement({ id: "m-1", movement_type: "purchase", amount: "30.00" }),
    ];

    render(<CurrentCycleTotalsSidebar movements={movements} />);

    expect(screen.getByText("Carried from previous cycle")).toBeInTheDocument();
    expect(screen.getByText("$200.00")).toBeInTheDocument();
    expect(screen.getByText("Interest")).toBeInTheDocument();
    expect(screen.getByText("$5.00")).toBeInTheDocument();
    // 200 + 5 + 30 - 0 payments = 235
    expect(screen.getByText("$235.00")).toBeInTheDocument();
  });

  it("hides zero-value rows (carried balance, interest, fees, refunds) but always shows payments made", () => {
    const movements = [movement({ id: "m-1", movement_type: "purchase", amount: "30.00" })];

    render(<CurrentCycleTotalsSidebar movements={movements} />);

    expect(screen.queryByText("Carried from previous cycle")).not.toBeInTheDocument();
    expect(screen.queryByText("Interest")).not.toBeInTheDocument();
    expect(screen.queryByText("Fees")).not.toBeInTheDocument();
    expect(screen.queryByText("Refunds")).not.toBeInTheDocument();
    expect(screen.getByText("Payments made")).toBeInTheDocument();
    expect(screen.getByText("$0.00")).toBeInTheDocument();
  });

  it("shows zero across the board for an empty movements table", () => {
    render(<CurrentCycleTotalsSidebar movements={[]} />);

    expect(screen.getByText("Left to pay")).toBeInTheDocument();
    expect(screen.getAllByText("$0.00").length).toBeGreaterThan(0);
  });
});
