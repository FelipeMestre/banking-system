import { afterEach, describe, expect, it, vi } from "vitest";
import { setAccessTokenGetter } from "../../../../lib/api/client";
import { getTransactions } from "../../../../features/transactions/api/get-transactions";

const PAGE_BODY = {
  items: [
    {
      id: "t1", request_id: "r1", type: "debit", amount: 1125,
      counterparty_account: "2222222222222222", decline_reason: null, ts: "2026-01-01T00:00:00Z",
    },
  ],
  next_cursor: "2026-01-01T00:00:00Z_t1",
};

describe("getTransactions", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("requests the account's transactions page and returns it", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(PAGE_BODY), { status: 200 }));

    const page = await getTransactions("1111111111111111", { limit: 20 });

    expect(page).toEqual(PAGE_BODY);
    const [url] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("/accounts/1111111111111111/transactions");
    expect(String(url)).toContain("limit=20");
  });

  it("includes the cursor when paginating", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(PAGE_BODY), { status: 200 }));

    await getTransactions("1111111111111111", { limit: 20, cursor: "abc_def" });

    const [url] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("cursor=abc_def");
  });

  it("throws a description of the failure on a non-2xx response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "not allowed" } }), { status: 403 }),
    );

    await expect(getTransactions("1111111111111111", { limit: 20 })).rejects.toThrow("not allowed");
  });
});
