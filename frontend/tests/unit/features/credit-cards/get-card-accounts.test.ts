import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, setAccessTokenGetter } from "@/lib/api/client";
import { getCardAccounts } from "@/features/credit-cards/api/get-card-accounts";

const PAGE_BODY = {
  items: [
    {
      card_account: {
        id: "ca-1", customer_id: "cust-1", paying_account_id: "acc-1",
        credit_limit: "1500.00", status: "active", used_credit: 15000,
      },
      card: {
        id: "card-1", card_account_id: "ca-1", card_number: "•••• •••• •••• 1234",
        expiration_date: "2029-01-01", status: "active",
      },
    },
  ],
  total: 1, limit: 50, offset: 0,
};

describe("getCardAccounts", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("requests card-accounts scoped by customer_id and returns the page", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(PAGE_BODY), { status: 200 }));

    const page = await getCardAccounts({ customerId: "cust-1", limit: 50, offset: 0 });

    expect(page).toEqual(PAGE_BODY);
    const requestedUrl = fetchSpy.mock.calls[0]?.[0] as string;
    expect(requestedUrl).toContain("customer_id=cust-1");
  });

  it("appends status to the query string when provided", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(PAGE_BODY), { status: 200 }));

    await getCardAccounts({ customerId: "cust-1", limit: 20, offset: 0, status: "active" });

    const requestedUrl = fetchSpy.mock.calls[0]?.[0] as string;
    expect(requestedUrl).toContain("status=active");
  });

  it("omits status from the query string when not provided", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(PAGE_BODY), { status: 200 }));

    await getCardAccounts({ customerId: "cust-1", limit: 20, offset: 0 });

    const requestedUrl = fetchSpy.mock.calls[0]?.[0] as string;
    expect(requestedUrl).not.toContain("status=");
  });

  it("throws an ApiError carrying the response status on a 500", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "boom" } }), { status: 500 }),
    );

    const error = await getCardAccounts({ customerId: "cust-1", limit: 50, offset: 0 }).catch(
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(500);
  });
});
