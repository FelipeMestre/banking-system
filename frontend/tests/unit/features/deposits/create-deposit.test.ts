import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, setAccessTokenGetter } from "@/lib/api/client";
import { createDeposit } from "@/features/deposits/api/create-deposit";

describe("createDeposit", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("POSTs to /admin/deposits with the exact body shape", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ request_id: "r1", approved: true, amount_applied: 5000, new_balance: 15000 }),
        { status: 200 },
      ),
    );

    await createDeposit({ account_number: "1234567890123456", amount: 5000, currency: "USD", reason: "test" });

    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(String(url)).toContain("/admin/deposits");
    expect(init?.method).toBe("POST");
    const headers = new Headers(init?.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(JSON.parse(init?.body as string)).toEqual({
      account_number: "1234567890123456",
      amount: 5000,
      currency: "USD",
      reason: "test",
    });
  });

  it("parses a successful response, including applied_rate when present", async () => {
    const appliedRate = {
      pair: "USD_EUR",
      mid_rate: 0.92,
      applied_rate: 0.9108,
      margin: 0.01,
      direction: "credit",
      source_ts: "2026-01-01T00:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          request_id: "r1",
          approved: true,
          amount_applied: 45540,
          applied_rate: appliedRate,
          new_balance: 195540,
        }),
        { status: 200 },
      ),
    );

    const result = await createDeposit({ account_number: "1234567890123456", amount: 50000, currency: "USD" });

    expect(result.amount_applied).toBe(45540);
    expect(result.applied_rate).toEqual(appliedRate);
    expect(result.new_balance).toBe(195540);
  });

  it("throws an ApiError with the surfaced detail on 404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "account not found" }), { status: 404 }),
    );

    await expect(
      createDeposit({ account_number: "1234567890123456", amount: 100, currency: "USD" }),
    ).rejects.toMatchObject({ message: "account not found", status: 404 });
  });

  it("rejects with an ApiError instance on failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "deposit confirmation timeout" }), { status: 504 }),
    );

    await expect(
      createDeposit({ account_number: "1234567890123456", amount: 100, currency: "USD" }),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
