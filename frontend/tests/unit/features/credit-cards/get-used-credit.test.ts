import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, setAccessTokenGetter } from "@/lib/api/client";
import { getUsedCredit } from "@/features/credit-cards/api/get-used-credit";

const BODY = {
  card_account_id: "ca-1", used_credit_estimate: "120.00", credit_limit: "1500.00",
  currency: "USD", is_estimate: true, movement_count: 3,
};

describe("getUsedCredit", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("requests the used-credit-estimate endpoint and surfaces is_estimate", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(BODY), { status: 200 }));

    const estimate = await getUsedCredit("ca-1");

    expect(estimate).toEqual(BODY);
    expect(estimate.is_estimate).toBe(true);
  });

  it("throws an ApiError carrying the response status on a 403 (not the owner)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "forbidden" } }), { status: 403 }),
    );

    await expect(getUsedCredit("ca-1")).rejects.toMatchObject({ status: 403 });
  });
});
