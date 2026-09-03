import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, setAccessTokenGetter } from "@/lib/api/client";
import { getAccounts } from "@/features/accounts/api/get-accounts";

const PAGE_BODY = {
  items: [
    {
      id: "a1", account_number: "1111111111111111", currency: "USD",
      customer_id: "c1", branch_id: "b1", balance: 0, status: "active",
    },
  ],
  total: 1, limit: 50, offset: 0,
};

describe("getAccounts", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("requests the accounts page and returns it", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(PAGE_BODY), { status: 200 }),
    );

    const page = await getAccounts({ limit: 50, offset: 0 });

    expect(page).toEqual(PAGE_BODY);
  });

  it("throws an ApiError carrying the response status on a 404 (no linked customer)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "no linked customer" } }), { status: 404 }),
    );

    await expect(getAccounts({ limit: 50, offset: 0 })).rejects.toMatchObject({
      status: 404,
      message: "no linked customer",
    });
  });

  it("throws an ApiError carrying the response status on a 500", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "boom" } }), { status: 500 }),
    );

    const error = await getAccounts({ limit: 50, offset: 0 }).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(500);
  });
});
