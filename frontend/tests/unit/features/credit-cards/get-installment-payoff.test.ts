import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, setAccessTokenGetter } from "@/lib/api/client";
import { getInstallmentPayoff } from "@/features/credit-cards/api/get-installment-payoff";

describe("getInstallmentPayoff", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("requests the installment payoff for a card account", async () => {
    const body = { card_account_id: "ca-1", payoff_amount: "300.00", currency: "USD" };
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));

    const result = await getInstallmentPayoff("ca-1");

    expect(result).toEqual(body);
    const requestedUrl = fetchSpy.mock.calls[0]?.[0] as string;
    expect(requestedUrl).toContain("/card-accounts/ca-1/installment-payoff");
  });

  it("throws an ApiError carrying the response status on failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "not found" } }), { status: 404 }),
    );

    const error = await getInstallmentPayoff("ca-1").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
  });
});
