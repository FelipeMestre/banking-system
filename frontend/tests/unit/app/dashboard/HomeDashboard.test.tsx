import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeDashboard } from "@/app/(dashboard)/HomeDashboard";

const ACCOUNTS_PAGE = {
  items: [
    {
      id: "a1", account_number: "1111111111111111", currency: "USD",
      customer_id: "c1", branch_id: "b1", balance: 250000, status: "active",
    },
    {
      id: "a2", account_number: "2222222222222222", currency: "EUR",
      customer_id: "c1", branch_id: "b1", balance: 100000, status: "active",
    },
  ],
  total: 2, limit: 50, offset: 0,
};

const TRANSACTIONS_PAGE = {
  items: [
    {
      id: "t1", request_id: "r1", type: "credit", amount: 96000,
      counterparty_account: "9999999999999999", decline_reason: null, ts: "2026-01-01T00:00:00Z",
    },
  ],
  next_cursor: null,
};

function mockFetchSequence() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/transactions")) {
      return new Response(JSON.stringify(TRANSACTIONS_PAGE), { status: 200 });
    }
    if (url.includes("/accounts")) {
      return new Response(JSON.stringify(ACCOUNTS_PAGE), { status: 200 });
    }
    throw new Error(`unexpected fetch: ${url}`);
  });
}

describe("HomeDashboard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the real, customer-scoped accounts and the selected account's transactions", async () => {
    mockFetchSequence();

    render(<HomeDashboard />);

    await waitFor(() => expect(screen.getAllByText("USD").length).toBeGreaterThan(0));
    expect(screen.getAllByText("EUR").length).toBeGreaterThan(0);

    await waitFor(() => expect(screen.getByText("9999999999999999")).toBeInTheDocument());
  });

  it("shows the empty-accounts state without an error when the customer has no accounts", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), { status: 200 }),
    );

    render(<HomeDashboard />);

    expect(await screen.findByText("You don't have any accounts yet")).toBeInTheDocument();
  });

  it("a 404 from getAccounts (no customer linked) shows the empty-accounts state with the KYC dialog, not plain error text", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "no linked customer" } }), { status: 404 }),
    );

    render(<HomeDashboard />);

    expect(await screen.findByText("You don't have any accounts yet")).toBeInTheDocument();
    expect(screen.queryByText("no linked customer")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create an account" }));

    expect(await screen.findByLabelText(/identification number/i)).toBeInTheDocument();
  });

  it("regression: a genuinely empty list (200, zero accounts) opens the dialog with no KYC fields", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), { status: 200 }),
    );

    render(<HomeDashboard />);

    fireEvent.click(await screen.findByRole("button", { name: "Create an account" }));

    expect(await screen.findByRole("button", { name: "Accept and open account" })).toBeInTheDocument();
    expect(screen.queryByLabelText(/identification number/i)).not.toBeInTheDocument();
  });

  it("regression: a genuine error (500) still surfaces plain error text, never the empty-accounts state", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "internal server error" } }), { status: 500 }),
    );

    render(<HomeDashboard />);

    expect(await screen.findByText("internal server error")).toBeInTheDocument();
    expect(screen.queryByText("You don't have any accounts yet")).not.toBeInTheDocument();
  });

  it("regression: a network error still surfaces plain error text, never the empty-accounts state", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));

    render(<HomeDashboard />);

    expect(await screen.findByText("network down")).toBeInTheDocument();
    expect(screen.queryByText("You don't have any accounts yet")).not.toBeInTheDocument();
  });

  it("regression: a 401 still surfaces plain error text, never the empty-accounts state", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "unauthorized" } }), { status: 401 }),
    );

    render(<HomeDashboard />);

    expect(await screen.findByText("unauthorized")).toBeInTheDocument();
    expect(screen.queryByText("You don't have any accounts yet")).not.toBeInTheDocument();
  });

  it("opens the T&C dialog, creates the account, and refetches the accounts list on success", async () => {
    let accountCreated = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/accounts/me") && init?.method === "POST") {
        accountCreated = true;
        return new Response(
          JSON.stringify({
            id: "a1", account_number: "1111111111111111", currency: "USD",
            customer_id: "c1", branch_id: "b1", balance: 0, status: "active",
          }),
          { status: 201 },
        );
      }
      if (url.includes("/transactions")) {
        return new Response(JSON.stringify(TRANSACTIONS_PAGE), { status: 200 });
      }
      if (url.includes("/accounts")) {
        return accountCreated
          ? new Response(JSON.stringify(ACCOUNTS_PAGE), { status: 200 })
          : new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), { status: 200 });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<HomeDashboard />);

    fireEvent.click(await screen.findByRole("button", { name: "Create an account" }));
    fireEvent.click(await screen.findByRole("button", { name: "Accept and open account" }));

    await waitFor(() => expect(screen.getAllByText("USD").length).toBeGreaterThan(0));
  });

  it("shows an inline error in the dialog and does not crash when creation fails with a 409", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/accounts/me") && init?.method === "POST") {
        return new Response(
          JSON.stringify({ error: { message: "customer already owns an account" } }),
          { status: 409 },
        );
      }
      return new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), { status: 200 });
    });

    render(<HomeDashboard />);

    fireEvent.click(await screen.findByRole("button", { name: "Create an account" }));
    fireEvent.click(await screen.findByRole("button", { name: "Accept and open account" }));

    expect(await screen.findByText("customer already owns an account")).toBeInTheDocument();
  });
});
