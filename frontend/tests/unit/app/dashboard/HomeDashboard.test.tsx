import { render, screen, waitFor } from "@testing-library/react";
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

    expect(await screen.findByText("You have no accounts yet.")).toBeInTheDocument();
  });

  it("surfaces a genuine error's message rather than crashing", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "internal server error" } }), { status: 500 }),
    );

    render(<HomeDashboard />);

    expect(await screen.findByText("internal server error")).toBeInTheDocument();
  });
});
