import { afterEach, describe, expect, it, vi } from "vitest";
import { setAccessTokenGetter } from "@/lib/api/client";
import { createAccount } from "@/features/accounts/api/create-account";

const ACCOUNT_BODY = {
  id: "a1", account_number: "1111111111111111", currency: "USD",
  customer_id: "c1", branch_id: "b1", balance: 0, status: "active",
};

describe("createAccount", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("posts to /accounts/me and returns the created account", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(ACCOUNT_BODY), { status: 201 }));

    const account = await createAccount();

    expect(account).toEqual(ACCOUNT_BODY);
    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(String(url)).toContain("/accounts/me");
    expect(init?.method).toBe("POST");
  });

  it("throws a description of the failure on a 409 race", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { message: "customer already owns an account" } }),
        { status: 409 },
      ),
    );

    await expect(createAccount()).rejects.toThrow("customer already owns an account");
  });

  it("throws on a network error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));

    await expect(createAccount()).rejects.toThrow("network down");
  });
});
