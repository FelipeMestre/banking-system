import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IssueCardAccountDialog } from "@/features/card-account-admin/components/IssueCardAccountDialog";
import * as issueModule from "@/features/card-account-admin/api/issue-card-account";
import * as getAccountsModule from "@/features/accounts/api/get-accounts";

const CUSTOMER_ID = "c-1";

const ACCOUNT = {
  id: "acc-1",
  account_number: "1234567890123456",
  currency: "USD",
  customer_id: CUSTOMER_ID,
  balance: 0,
  status: "active" as const,
};

function stubAccounts() {
  return vi.spyOn(getAccountsModule, "getAllAccountsForCustomer").mockResolvedValue({
    items: [ACCOUNT],
    total: 1,
    limit: 200,
    offset: 0,
  });
}

async function fillForm() {
  // Wait for the account list to finish loading — the trigger stays
  // disabled (and won't open) while `getAllAccountsForCustomer` is pending.
  await screen.findByText("Select an account");
  fireEvent.click(screen.getByRole("combobox", { name: /paying account/i }));
  fireEvent.click(await screen.findByRole("option", { name: /1234567890123456 — USD/ }));
  fireEvent.change(screen.getByLabelText(/credit limit/i), { target: { value: "1000.00" } });
}

describe("IssueCardAccountDialog", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps Issue disabled until the required fields are filled", async () => {
    stubAccounts();
    render(<IssueCardAccountDialog customerId={CUSTOMER_ID} onClose={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Issue" })).toBeDisabled();
    await fillForm();
    expect(screen.getByRole("button", { name: "Issue" })).toBeEnabled();
  });

  it("fetches accounts scoped to the customer prop, not a re-picked customer", async () => {
    const spy = stubAccounts();
    render(<IssueCardAccountDialog customerId={CUSTOMER_ID} onClose={vi.fn()} onSuccess={vi.fn()} />);

    await screen.findByText("Select an account");
    expect(spy).toHaveBeenCalledWith({ customerId: CUSTOMER_ID, limit: 200, offset: 0 });
    expect(screen.queryByLabelText(/customer/i)).not.toBeInTheDocument();
  });

  it("issues the card account and calls onSuccess on the happy path", async () => {
    stubAccounts();
    const issueSpy = vi.spyOn(issueModule, "issueCardAccount").mockResolvedValue({
      card_account: { id: "ca-1", customer_id: CUSTOMER_ID, paying_account_id: "acc-1", credit_limit: "1000.00", status: "active" },
      card: { id: "card-1", card_account_id: "ca-1", card_number: "4111111111111234", expiration_date: "2030-01-01", status: "active" },
    });
    const onSuccess = vi.fn();
    render(<IssueCardAccountDialog customerId={CUSTOMER_ID} onClose={vi.fn()} onSuccess={onSuccess} />);

    await fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Issue" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    expect(issueSpy).toHaveBeenCalledWith({
      customer_id: CUSTOMER_ID,
      paying_account_id: "acc-1",
      credit_limit: "1000.00",
      reason: undefined,
    });
  });

  it("surfaces a 422 validation failure inline", async () => {
    stubAccounts();
    vi.spyOn(issueModule, "issueCardAccount").mockRejectedValue(
      new Error("The gateway rejected those values. Check the accounts and amount."),
    );
    render(<IssueCardAccountDialog customerId={CUSTOMER_ID} onClose={vi.fn()} onSuccess={vi.fn()} />);

    await fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Issue" }));

    expect(
      await screen.findByText("The gateway rejected those values. Check the accounts and amount."),
    ).toBeInTheDocument();
  });

  it("surfaces a 401 invalid-admin-identity failure inline", async () => {
    stubAccounts();
    vi.spyOn(issueModule, "issueCardAccount").mockRejectedValue(
      new Error("Not authenticated. Please log in again."),
    );
    render(<IssueCardAccountDialog customerId={CUSTOMER_ID} onClose={vi.fn()} onSuccess={vi.fn()} />);

    await fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Issue" }));

    expect(await screen.findByText("Not authenticated. Please log in again.")).toBeInTheDocument();
  });

  it("shows an empty state and keeps Issue disabled when the customer has no accounts", async () => {
    vi.spyOn(getAccountsModule, "getAllAccountsForCustomer").mockResolvedValue({
      items: [],
      total: 0,
      limit: 200,
      offset: 0,
    });
    render(<IssueCardAccountDialog customerId={CUSTOMER_ID} onClose={vi.fn()} onSuccess={vi.fn()} />);

    expect(await screen.findByText("No accounts for this customer.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Issue" })).toBeDisabled();
  });
});
