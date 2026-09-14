import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, setAccessTokenGetter } from "@/lib/api/client";
import { getStatements } from "@/features/credit-cards/api/get-statements";

const STATEMENTS = [
  {
    id: "st-1", card_account_id: "ca-1", period_start: "2026-07-20", period_end: "2026-08-20",
    due_date: "2026-09-10", purchases_total: "100.00", interest_total: "0.00", total_due: "100.00",
    paid_amount: "0.00", credit_balance: "0.00", late_fees_total: "0.00", minimum_payment: "10.00",
    paid_in_full: false, paid_by_due_date: false, status: "closed",
    created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z",
  },
];

describe("getStatements", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("requests the statements list for a card account", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(STATEMENTS), { status: 200 }));

    const rows = await getStatements({ cardAccountId: "ca-1" });

    expect(rows).toEqual(STATEMENTS);
    const requestedUrl = fetchSpy.mock.calls[0]?.[0] as string;
    expect(requestedUrl).toContain("/card-accounts/ca-1/statements");
  });

  it("includes an explicit limit when given", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(STATEMENTS), { status: 200 }));

    await getStatements({ cardAccountId: "ca-1", limit: 5 });

    const requestedUrl = fetchSpy.mock.calls[0]?.[0] as string;
    expect(requestedUrl).toContain("limit=5");
  });

  it("throws an ApiError carrying the response status on failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "forbidden" } }), { status: 403 }),
    );

    const error = await getStatements({ cardAccountId: "ca-1" }).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
  });
});
