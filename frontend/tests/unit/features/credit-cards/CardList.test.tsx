import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CardList } from "@/features/credit-cards/components/CardList";
import type { CardAccountListItem } from "@/features/credit-cards/types";

const TWO_CARDS: CardAccountListItem[] = [
  {
    card_account: { id: "ca-1", customer_id: "c1", paying_account_id: "a1", credit_limit: "1500.00", status: "active" },
    card: { id: "card-1", card_account_id: "ca-1", card_number: "•••• •••• •••• 1234", expiration_date: "2029-01-01", status: "active" },
  },
  {
    card_account: { id: "ca-2", customer_id: "c1", paying_account_id: "a1", credit_limit: "500.00", status: "blocked" },
    card: { id: "card-2", card_account_id: "ca-2", card_number: "•••• •••• •••• 5678", expiration_date: "2027-06-01", status: "blocked" },
  },
];

describe("CardList", () => {
  it("renders both cards with correct masked number, status, and credit limit", () => {
    render(<CardList items={TWO_CARDS} selectedCardAccountId={null} onSelect={vi.fn()} />);

    expect(screen.getByText("•••• •••• •••• 1234")).toBeInTheDocument();
    expect(screen.getByText("•••• •••• •••• 5678")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("blocked")).toBeInTheDocument();
    expect(screen.getByText("Limit $1500.00")).toBeInTheDocument();
    expect(screen.getByText("Limit $500.00")).toBeInTheDocument();
  });

  it("calls onSelect with the clicked card account's id", () => {
    const onSelect = vi.fn();
    render(<CardList items={TWO_CARDS} selectedCardAccountId={null} onSelect={onSelect} />);

    screen.getByText("•••• •••• •••• 5678").closest("button")!.click();

    expect(onSelect).toHaveBeenCalledWith("ca-2");
  });

  it("renders an empty state when the customer has no cards", () => {
    render(<CardList items={[]} selectedCardAccountId={null} onSelect={vi.fn()} />);

    expect(screen.getByText("You have no credit cards yet.")).toBeInTheDocument();
  });
});
