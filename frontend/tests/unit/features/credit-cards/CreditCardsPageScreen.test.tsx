import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CreditCardsPageScreen } from "@/features/credit-cards/components/CreditCardsPageScreen";
import * as customerModule from "@/features/credit-cards/api/get-current-customer";
import * as cardAccountsModule from "@/features/credit-cards/api/get-card-accounts";
import * as usedCreditModule from "@/features/credit-cards/api/get-used-credit";
import * as movementsModule from "@/features/credit-cards/api/get-movements";
import type { CardAccountListItem } from "@/features/credit-cards/types";
import type { Page } from "@/lib/api/types";

const CARD_ACCOUNTS_PAGE: Page<CardAccountListItem> = {
  items: [
    {
      card_account: { id: "ca-1", customer_id: "cust-1", paying_account_id: "a1", credit_limit: "1500.00", status: "active" },
      card: { id: "card-1", card_account_id: "ca-1", card_number: "•••• •••• •••• 1234", expiration_date: "2029-01-01", status: "active" },
    },
    {
      card_account: { id: "ca-2", customer_id: "cust-1", paying_account_id: "a1", credit_limit: "500.00", status: "active" },
      card: { id: "card-2", card_account_id: "ca-2", card_number: "•••• •••• •••• 5678", expiration_date: "2027-06-01", status: "active" },
    },
  ],
  total: 2, limit: 50, offset: 0,
};

describe("CreditCardsPageScreen", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows both of the customer's cards once loaded", async () => {
    vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
    vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue(CARD_ACCOUNTS_PAGE);
    vi.spyOn(usedCreditModule, "getUsedCredit").mockResolvedValue({
      card_account_id: "ca-1", used_credit_estimate: "0.00", credit_limit: "1500.00",
      currency: "USD", is_estimate: true, movement_count: 0,
    });
    vi.spyOn(movementsModule, "getMovements").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

    render(<CreditCardsPageScreen />);

    expect(await screen.findByText("•••• •••• •••• 1234")).toBeInTheDocument();
    expect(screen.getByText("•••• •••• •••• 5678")).toBeInTheDocument();
    await waitFor(() => expect(usedCreditModule.getUsedCredit).toHaveBeenCalledWith("ca-1"));
  });

  it("renders none of Phase-4's billing UI anywhere on the page", async () => {
    vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
    vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue(CARD_ACCOUNTS_PAGE);
    vi.spyOn(usedCreditModule, "getUsedCredit").mockResolvedValue({
      card_account_id: "ca-1", used_credit_estimate: "0.00", credit_limit: "1500.00",
      currency: "USD", is_estimate: true, movement_count: 0,
    });
    vi.spyOn(movementsModule, "getMovements").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

    render(<CreditCardsPageScreen />);
    await screen.findByText("•••• •••• •••• 1234");

    for (const forbidden of [
      /minimum payment/i, /due date/i, /closing date/i, /billing cycle/i,
      /late fee/i, /statement/i, /download.*pdf/i, /coming soon/i,
      /renew card/i, /block card/i, /issue card/i,
    ]) {
      expect(screen.queryByText(forbidden)).not.toBeInTheDocument();
    }
  });
});
