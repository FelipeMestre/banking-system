import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, setAccessTokenGetter } from "@/lib/api/client";
import { getCurrentCustomer } from "@/features/credit-cards/api/get-current-customer";

describe("getCurrentCustomer", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("requests /customers/me and returns the resolved identity", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "cust-1" }), { status: 200 }),
    );

    const customer = await getCurrentCustomer();

    expect(customer).toEqual({ id: "cust-1" });
  });

  it("throws an ApiError carrying the response status on a 404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "no linked customer" } }), { status: 404 }),
    );

    await expect(getCurrentCustomer()).rejects.toMatchObject({ status: 404 });
    await expect(getCurrentCustomer()).rejects.toBeInstanceOf(ApiError);
  });
});
