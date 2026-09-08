import { afterEach, describe, expect, it, vi } from "vitest";
import { setAccessTokenGetter } from "@/lib/api/client";
import { issueCardAccount } from "@/features/card-account-admin/api/issue-card-account";
import { updateCreditLimit } from "@/features/card-account-admin/api/update-credit-limit";
import { updateCardAccountStatus } from "@/features/card-account-admin/api/update-card-account-status";
import { renewCard } from "@/features/card-account-admin/api/renew-card";
import { updateCardStatus } from "@/features/card-account-admin/api/update-card-status";

describe("card-account-admin api", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("issueCardAccount posts to /card-accounts", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ card_account: {}, card: {} }), { status: 201 }),
      );

    await issueCardAccount({ customer_id: "c-1", paying_account_id: "acc-1", credit_limit: "10.00" });

    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(String(url)).toContain("/card-accounts");
    expect(init?.method).toBe("POST");
  });

  it("issueCardAccount surfaces a 401 InvalidAdminIdentityError message verbatim", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "admin identity is missing" } }), { status: 401 }),
    );

    await expect(
      issueCardAccount({ customer_id: "c-1", paying_account_id: "acc-1", credit_limit: "10.00" }),
    ).rejects.toThrow("admin identity is missing");
  });

  it("updateCreditLimit PUTs to /card-accounts/{id}", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await updateCreditLimit("ca-1", { credit_limit: "20.00" });

    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(String(url)).toContain("/card-accounts/ca-1");
    expect(init?.method).toBe("PUT");
  });

  it("updateCardAccountStatus posts to /card-accounts/{id}/status and surfaces the 409 message", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { message: "card account ca-1 cannot be closed: outstanding balance 5.00" } }),
        { status: 409 },
      ),
    );

    await expect(updateCardAccountStatus("ca-1", { status: "closed" })).rejects.toThrow(
      "card account ca-1 cannot be closed: outstanding balance 5.00",
    );
  });

  it("renewCard posts to /card-accounts/{id}/cards with an empty default body", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 201 }));

    await renewCard("ca-1");

    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(String(url)).toContain("/card-accounts/ca-1/cards");
    expect(init?.body).toBe("{}");
  });

  it("updateCardStatus posts to /cards/{card_number}/status using the real card number", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await updateCardStatus("4111111111111234", { status: "blocked" });

    const [url] = fetchSpy.mock.calls[0]!;
    expect(String(url)).toContain("/cards/4111111111111234/status");
  });
});
