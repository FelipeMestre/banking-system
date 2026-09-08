import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, setAccessTokenGetter } from "@/lib/api/client";
import { requestPayment } from "@/features/credit-cards/api/request-payment";

describe("requestPayment", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("posts the cents amount and returns the accepted request", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ request_id: "r1", status: "pending" }), { status: 202 }),
    );

    const accepted = await requestPayment("ca-1", { amount: 20000, source_account: "1111222233334444" });

    expect(accepted).toEqual({ request_id: "r1", status: "pending" });
    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ amount: 20000, source_account: "1111222233334444" });
  });

  it("throws an ApiError carrying the response status on a 409 (no active card)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "no active card" } }), { status: 409 }),
    );

    const body = { amount: 100, source_account: "1111222233334444" };
    await expect(requestPayment("ca-1", body)).rejects.toMatchObject({ status: 409 });
    await expect(requestPayment("ca-1", body)).rejects.toBeInstanceOf(ApiError);
  });
});
