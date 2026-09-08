import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountPicker } from "@/features/card-account-admin/components/AccountPicker";
import * as getAccountsModule from "@/features/accounts/api/get-accounts";

const ACCOUNT_A = {
  id: "acc-a",
  account_number: "1111111111111111",
  currency: "USD",
  customer_id: "customer-a",
  branch_id: "b-1",
  balance: 0,
  status: "active" as const,
};

const ACCOUNT_B = {
  id: "acc-b",
  account_number: "2222222222222222",
  currency: "EUR",
  customer_id: "customer-b",
  branch_id: "b-1",
  balance: 0,
  status: "active" as const,
};

describe("AccountPicker", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads accounts for the given customerId", async () => {
    const spy = vi.spyOn(getAccountsModule, "getAllAccountsForCustomer").mockResolvedValue({
      items: [ACCOUNT_A],
      total: 1,
      limit: 200,
      offset: 0,
    });

    render(<AccountPicker customerId="customer-a" value={null} onChange={vi.fn()} />);

    await screen.findByText("Select an account");
    expect(spy).toHaveBeenCalledWith({ customerId: "customer-a", limit: 200, offset: 0 });

    fireEvent.click(screen.getByRole("combobox", { name: /paying account/i }));
    expect(await screen.findByRole("option", { name: "1111111111111111 — USD" })).toBeInTheDocument();
  });

  it("re-fetches when customerId changes", async () => {
    const spy = vi
      .spyOn(getAccountsModule, "getAllAccountsForCustomer")
      .mockResolvedValueOnce({ items: [ACCOUNT_A], total: 1, limit: 200, offset: 0 })
      .mockResolvedValueOnce({ items: [ACCOUNT_B], total: 1, limit: 200, offset: 0 });

    const { rerender } = render(<AccountPicker customerId="customer-a" value={null} onChange={vi.fn()} />);
    await screen.findByText("Select an account");
    expect(spy).toHaveBeenNthCalledWith(1, { customerId: "customer-a", limit: 200, offset: 0 });

    rerender(<AccountPicker customerId="customer-b" value={null} onChange={vi.fn()} />);
    await screen.findByText("Select an account");
    expect(spy).toHaveBeenNthCalledWith(2, { customerId: "customer-b", limit: 200, offset: 0 });
  });

  it("shows an empty state when the customer has no accounts", async () => {
    vi.spyOn(getAccountsModule, "getAllAccountsForCustomer").mockResolvedValue({
      items: [],
      total: 0,
      limit: 200,
      offset: 0,
    });

    render(<AccountPicker customerId="customer-a" value={null} onChange={vi.fn()} />);

    expect(await screen.findByText("No accounts for this customer.")).toBeInTheDocument();
  });

  it("surfaces a load failure", async () => {
    vi.spyOn(getAccountsModule, "getAllAccountsForCustomer").mockRejectedValue(new Error("Network error."));

    render(<AccountPicker customerId="customer-a" value={null} onChange={vi.fn()} />);

    expect(await screen.findByText("Network error.")).toBeInTheDocument();
  });
});
