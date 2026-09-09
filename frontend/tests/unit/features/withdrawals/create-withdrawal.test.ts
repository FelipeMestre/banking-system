import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, setAccessTokenGetter } from "@/lib/api/client";
import { createWithdrawal } from "@/features/withdrawals/api/create-withdrawal";

describe("createWithdrawal", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("POSTs to /admin/withdrawals with the exact body shape", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ request_id: "r1", approved: true, amount_applied: 5000, new_balance: 5000 }),
        { status: 200 },
      ),
    );

    await createWithdrawal({ account_number: "1234567890123456", amount: 5000, currency: "USD", reason: "test" });

    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(String(url)).toContain("/admin/withdrawals");
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

  it("parses a successful (approved) response, including applied_rate when present", async () => {
    const appliedRate = {
      pair: "USD_EUR",
      mid_rate: 0.92,
      applied_rate: 0.9108,
      margin: 0.01,
      direction: "debit",
      source_ts: "2026-01-01T00:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          request_id: "r1",
          approved: true,
          amount_applied: 45540,
          applied_rate: appliedRate,
          new_balance: 4460,
        }),
        { status: 200 },
      ),
    );

    const result = await createWithdrawal({ account_number: "1234567890123456", amount: 50000, currency: "USD" });

    expect(result.approved).toBe(true);
    expect(result.amount_applied).toBe(45540);
    expect(result.applied_rate).toEqual(appliedRate);
    expect(result.new_balance).toBe(4460);
  });

  it("resolves (does not throw) a declined response — HTTP 200 with approved: false", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ request_id: "r1", approved: false, reason: "insufficient_funds" }),
        { status: 200 },
      ),
    );

    const result = await createWithdrawal({ account_number: "1234567890123456", amount: 100, currency: "USD" });

    expect(result.approved).toBe(false);
    expect(result.reason).toBe("insufficient_funds");
    expect(result.amount_applied).toBeUndefined();
    expect(result.new_balance).toBeUndefined();
  });

  it("throws an ApiError with the surfaced detail on 404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "account not found" }), { status: 404 }),
    );

    await expect(
      createWithdrawal({ account_number: "1234567890123456", amount: 100, currency: "USD" }),
    ).rejects.toMatchObject({ message: "account not found", status: 404 });
  });

  it("rejects with an ApiError instance on a genuine server failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "withdrawal confirmation timeout" }), { status: 504 }),
    );

    await expect(
      createWithdrawal({ account_number: "1234567890123456", amount: 100, currency: "USD" }),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
