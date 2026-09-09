import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CreditCardPanel } from "@/components/home/CreditCardPanel";
import * as customerModule from "@/features/credit-cards/api/get-current-customer";
import * as cardAccountsModule from "@/features/credit-cards/api/get-card-accounts";
import type { CardAccountListItem } from "@/features/credit-cards";
import type { Page } from "@/lib/api/types";

function item(overrides: {
  id: string;
  creditLimit: string;
  usedCredit: number;
  cardNumber: string;
}): CardAccountListItem {
  return {
    card_account: {
      id: overrides.id,
      customer_id: "cust-1",
      paying_account_id: "a1",
      credit_limit: overrides.creditLimit,
      status: "active",
      used_credit: overrides.usedCredit,
    },
    card: {
      id: `card-${overrides.id}`,
      card_account_id: overrides.id,
      card_number: overrides.cardNumber,
      expiration_date: "2029-01-01",
      status: "active",
    },
  };
}

describe("CreditCardPanel (homepage)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the real used/available/total limit for the customer's only card", async () => {
    vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
    vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue({
      items: [item({ id: "ca-1", creditLimit: "1500.00", usedCredit: 35000, cardNumber: "•••• •••• •••• 1234" })],
      total: 1, limit: 50, offset: 0,
    } as Page<CardAccountListItem>);

    render(<CreditCardPanel />);

    expect(await screen.findByText("•••• •••• •••• 1234")).toBeInTheDocument();
    expect(screen.getByText("1,150.00")).toBeInTheDocument();
    expect(screen.getByText("$350.00 used")).toBeInTheDocument();
    expect(screen.getByText("of $1,500.00")).toBeInTheDocument();
  });

  it("defaults to the card with the biggest credit limit when the customer has several", async () => {
    vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
    vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue({
      items: [
        item({ id: "ca-1", creditLimit: "500.00", usedCredit: 0, cardNumber: "•••• •••• •••• 1111" }),
        item({ id: "ca-2", creditLimit: "5000.00", usedCredit: 0, cardNumber: "•••• •••• •••• 2222" }),
        item({ id: "ca-3", creditLimit: "1500.00", usedCredit: 0, cardNumber: "•••• •••• •••• 3333" }),
      ],
      total: 3, limit: 50, offset: 0,
    } as Page<CardAccountListItem>);

    render(<CreditCardPanel />);

    expect(await screen.findByText("•••• •••• •••• 2222")).toBeInTheDocument();
    expect(screen.queryByText("•••• •••• •••• 1111")).not.toBeInTheDocument();
    expect(screen.queryByText("•••• •••• •••• 3333")).not.toBeInTheDocument();
  });

  it("renders nothing when the customer has no cards", async () => {
    vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
    vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue({
      items: [], total: 0, limit: 50, offset: 0,
    } as Page<CardAccountListItem>);

    const { container } = render(<CreditCardPanel />);

    await waitFor(() => expect(cardAccountsModule.getCardAccounts).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing, not an error, when the card accounts request fails", async () => {
    vi.spyOn(customerModule, "getCurrentCustomer").mockRejectedValue(new Error("gateway unreachable"));

    const { container } = render(<CreditCardPanel />);

    await waitFor(() => expect(customerModule.getCurrentCustomer).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
