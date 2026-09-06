import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, setAccessTokenGetter } from "@/lib/api/client";
import { getMovements } from "@/features/credit-cards/api/get-movements";

const PAGE_BODY = {
  items: [
    {
      id: "m1", movement_type: "purchase", amount: "58.64", currency: "USD",
      occurred_at: "2026-09-04T12:00:00Z", fx_pair: "EUR/USD", fx_applied_rate: "1.1727",
    },
  ],
  total: 1, limit: 20, offset: 0,
};

describe("getMovements", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("requests paginated movements for a card account", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(PAGE_BODY), { status: 200 }));

    const page = await getMovements({ cardAccountId: "ca-1", limit: 20, offset: 0 });

    expect(page).toEqual(PAGE_BODY);
    const requestedUrl = fetchSpy.mock.calls[0]?.[0] as string;
    expect(requestedUrl).toContain("/card-accounts/ca-1/movements");
    expect(requestedUrl).toContain("limit=20");
  });

  it("throws an ApiError carrying the response status on a 404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "not found" } }), { status: 404 }),
    );

    const error = await getMovements({ cardAccountId: "ca-1", limit: 20, offset: 0 }).catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(ApiError);
  });
});
