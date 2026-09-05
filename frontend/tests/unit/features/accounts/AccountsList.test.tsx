import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setAccessTokenGetter } from "@/lib/api/client";
import { AccountsList } from "@/features/accounts/components/AccountsList";

const ACCOUNT = {
  id: "a1",
  account_number: "1111111111111111",
  currency: "USD",
  customer_id: "c1",
  branch_id: "b1",
  balance: 0,
  status: "active",
};

function pageFetch() {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({ items: [ACCOUNT], total: 1, limit: 10, offset: 0 }),
      { status: 200 },
    ),
  );
}

describe("AccountsList scope", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("defaults to the customer-scoped /accounts endpoint", async () => {
    const fetchSpy = pageFetch();

    render(<AccountsList />);

    await waitFor(() => expect(screen.getByText("1111111111111111")).toBeInTheDocument());
    const url = String(fetchSpy.mock.calls[0]?.[0]);
    expect(url).toContain("/accounts?");
    expect(url).not.toContain("/accounts/all");
  });

  it('scope="all" hits the cross-customer /accounts/all endpoint', async () => {
    const fetchSpy = pageFetch();

    render(<AccountsList scope="all" />);

    await waitFor(() => expect(screen.getByText("1111111111111111")).toBeInTheDocument());
    const url = String(fetchSpy.mock.calls[0]?.[0]);
    expect(url).toContain("/accounts/all?");
  });
});
