import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MovementsList } from "@/features/credit-cards/components/MovementsList";
import type { CardMovement } from "@/features/credit-cards/types";

describe("MovementsList", () => {
  it("shows an FX purchase's original amount and applied rate", () => {
    const fxMovement: CardMovement = {
      id: "m1", movement_type: "purchase", amount: "58.64", currency: "USD",
      occurred_at: "2026-09-04T00:00:00Z", fx_pair: "EUR/USD", fx_applied_rate: "1.1727",
    };

    render(<MovementsList items={[fxMovement]} />);

    expect(screen.getByText("EUR/USD · rate 1.1727")).toBeInTheDocument();
  });

  it("shows an installment purchase's position as Installment N of M", () => {
    const installmentMovement: CardMovement = {
      id: "m2", movement_type: "purchase", amount: "19.55", currency: "USD",
      occurred_at: "2026-09-04T00:00:00Z", installment_count: 3, installment_amount: "19.55",
    };

    render(<MovementsList items={[installmentMovement]} />);

    expect(screen.getByText(/Installment 1 of 3/)).toBeInTheDocument();
  });

  it("shows the decline reason and styles a declined row distinctly from an approved purchase", () => {
    const declined: CardMovement = {
      id: "m3", movement_type: "declined", amount: "999.00", currency: "USD",
      occurred_at: "2026-09-04T00:00:00Z", decline_reason: "insufficient_credit",
    };
    const approved: CardMovement = {
      id: "m4", movement_type: "purchase", amount: "10.00", currency: "USD",
      occurred_at: "2026-09-04T00:00:00Z",
    };

    render(<MovementsList items={[declined, approved]} />);

    expect(screen.getByText("Reason: insufficient_credit")).toBeInTheDocument();
    const declinedRow = screen.getByText("Reason: insufficient_credit").closest("li")!;
    const approvedRow = screen.getByText("Card purchase").closest("li")!;
    expect(declinedRow.className).not.toBe(approvedRow.className);
  });

  it("visually distinguishes a purchase from a payment via sign, color, and label", () => {
    const purchase: CardMovement = {
      id: "m5", movement_type: "purchase", amount: "50.00", currency: "USD", occurred_at: "2026-09-04T00:00:00Z",
    };
    const payment: CardMovement = {
      id: "m6", movement_type: "payment", amount: "30.00", currency: "USD", occurred_at: "2026-09-04T00:00:00Z",
    };

    render(<MovementsList items={[purchase, payment]} />);

    // A purchase owes more: shown plain (no sign), colored as the "increase" tone.
    const purchaseAmount = screen.getByText("$50.00");
    expect(purchaseAmount).toBeInTheDocument();
    expect(purchaseAmount.className).toContain("text-destructive");

    // A payment reduces what's owed: shown with a leading "+".
    const paymentAmount = screen.getByText("+$30.00");
    expect(paymentAmount).toBeInTheDocument();
    expect(paymentAmount.className).not.toContain("text-destructive");

    expect(screen.getAllByText("Purchase")).toHaveLength(1);
    expect(screen.getAllByText("Payment")).toHaveLength(1);
  });

  it("shows a positive icon for an approved movement and a cross for a declined one", () => {
    const approved: CardMovement = {
      id: "m7", movement_type: "payment", amount: "300.00", currency: "USD", occurred_at: "2026-09-10T00:00:00Z",
    };
    const declined: CardMovement = {
      id: "m8", movement_type: "declined", amount: "899.00", currency: "USD", occurred_at: "2026-09-12T00:00:00Z",
    };

    render(<MovementsList items={[approved, declined]} />);

    const approvedRow = screen.getByText("Payment received").closest("li")!;
    const declinedRow = screen.getByText("Attempted purchase").closest("li")!;
    expect(approvedRow.querySelector("svg.lucide-circle-check")).toBeTruthy();
    expect(declinedRow.querySelector("svg.lucide-circle-x")).toBeTruthy();
  });

  it("shows the movement date", () => {
    const movement: CardMovement = {
      id: "m9", movement_type: "purchase", amount: "18.40", currency: "USD",
      occurred_at: "2026-09-02T00:00:00Z", description: "Blue Bottle Coffee",
    };

    render(<MovementsList items={[movement]} />);

    expect(screen.getByText("Sep 2")).toBeInTheDocument();
  });
});
