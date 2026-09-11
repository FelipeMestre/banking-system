import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PayBillDialog } from "@/features/credit-cards/components/PayBillDialog";
import * as customerModule from "@/features/credit-cards/api/get-current-customer";
import * as cardAccountsModule from "@/features/credit-cards/api/get-card-accounts";
import * as statementsModule from "@/features/credit-cards/api/get-statements";
import * as payoffModule from "@/features/credit-cards/api/get-installment-payoff";
import * as accountsModule from "@/features/accounts/api/get-accounts";
import type { CardAccountListItem, Statement } from "@/features/credit-cards/types";
import type { Page } from "@/lib/api/types";

const CARD_ACCOUNTS_PAGE: Page<CardAccountListItem> = {
  items: [
    {
      card_account: { id: "ca-1", customer_id: "cust-1", paying_account_id: "a1", credit_limit: "1500.00", status: "active", used_credit: 15000 },
      card: { id: "card-1", card_account_id: "ca-1", card_number: "•••• •••• •••• 1234", expiration_date: "2029-01-01", status: "active" },
    },
    {
      card_account: { id: "ca-2", customer_id: "cust-1", paying_account_id: "a1", credit_limit: "500.00", status: "active", used_credit: 0 },
      card: { id: "card-2", card_account_id: "ca-2", card_number: "•••• •••• •••• 5678", expiration_date: "2027-06-01", status: "active" },
    },
  ],
  total: 2, limit: 50, offset: 0,
};

const LATEST_STATEMENT: Statement = {
  id: "st-1", card_account_id: "ca-1", period_start: "2026-08-01", period_end: "2026-08-31",
  due_date: "2026-09-21", purchases_total: "150.00", interest_total: "0.00", total_due: "150.00",
  paid_amount: "0.00", credit_balance: "0.00", late_fees_total: "0.00", minimum_payment: "35.00",
  paid_in_full: false, paid_by_due_date: false, status: "closed",
  created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z", payable: true,
};

function mockCommonApis() {
  vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
  vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue(CARD_ACCOUNTS_PAGE);
  vi.spyOn(statementsModule, "getStatements").mockResolvedValue([LATEST_STATEMENT]);
  vi.spyOn(payoffModule, "getInstallmentPayoff").mockResolvedValue({
    card_account_id: "ca-1", payoff_amount: "0.00", currency: "USD",
  });
  vi.spyOn(accountsModule, "getAccounts").mockResolvedValue({
    items: [{ id: "a1", account_number: "1111222233334444", currency: "USD", customer_id: "cust-1", balance: 500000, status: "active" }],
    total: 1, limit: 50, offset: 0,
  });
}

describe("PayBillDialog", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows both of the customer's cards to choose from", async () => {
    mockCommonApis();
    render(<PayBillDialog onClose={vi.fn()} />);

    expect(await screen.findByText("•••• •••• •••• 1234")).toBeInTheDocument();
    expect(screen.getByText("•••• •••• •••• 5678")).toBeInTheDocument();
  });

  it("picking a card advances straight to PayDialog, preset to that card's latest cycle", async () => {
    mockCommonApis();
    render(<PayBillDialog onClose={vi.fn()} />);

    fireEvent.click(await screen.findByText("•••• •••• •••• 1234"));

    expect(await screen.findByText("Pay your card")).toBeInTheDocument();
    expect(statementsModule.getStatements).toHaveBeenCalledWith({ cardAccountId: "ca-1", limit: 1 });

    // The latest cycle's totals show up as quick-select presets.
    expect(await screen.findByText(/Pay minimum/)).toBeInTheDocument();
    expect(screen.getByText(/Pay in full/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Pay in full/ }));
    expect(screen.getByLabelText("Amount")).toHaveValue("150.00");
  });

  it("shows an empty state when the customer has no cards", async () => {
    mockCommonApis();
    vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue({
      items: [], total: 0, limit: 50, offset: 0,
    });
    render(<PayBillDialog onClose={vi.fn()} />);

    expect(await screen.findByText("You have no credit cards yet.")).toBeInTheDocument();
  });

  it("closing the card-selection step calls onClose", async () => {
    mockCommonApis();
    const onClose = vi.fn();
    render(<PayBillDialog onClose={onClose} />);
    await screen.findByText("•••• •••• •••• 1234");

    // The dialog's own "X" icon button is separately aria-labeled "Close" —
    // scope to the visible text so this targets only the footer button.
    fireEvent.click(screen.getByText("Close"));

    expect(onClose).toHaveBeenCalledOnce();
  });
});
