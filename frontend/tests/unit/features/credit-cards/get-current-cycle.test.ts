import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, setAccessTokenGetter } from "@/lib/api/client";
import { getCurrentCycle } from "@/features/credit-cards/api/get-current-cycle";

const PROJECTION_BODY = {
  period_start: "2026-08-21",
  projected_period_end: "2026-09-20",
  overdue_from_previous_cycle: null,
  interest_on_overdue: null,
  new_purchases_this_cycle: "60.00",
  total_to_pay: "60.00",
  payable: true,
};

describe("getCurrentCycle", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("requests the live current-cycle projection for a card account", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(PROJECTION_BODY), { status: 200 }));

    const projection = await getCurrentCycle({ cardAccountId: "ca-1" });

    expect(projection).toEqual(PROJECTION_BODY);
    const requestedUrl = fetchSpy.mock.calls[0]?.[0] as string;
    expect(requestedUrl).toContain("/card-accounts/ca-1/current-cycle");
  });

  it("preserves absent overdue/interest fields as null, never zero", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(PROJECTION_BODY), { status: 200 }),
    );

    const projection = await getCurrentCycle({ cardAccountId: "ca-1" });

    expect(projection.overdue_from_previous_cycle).toBeNull();
    expect(projection.interest_on_overdue).toBeNull();
  });

  it("throws an ApiError carrying the response status on a failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "not found" } }), { status: 404 }),
    );

    const error = await getCurrentCycle({ cardAccountId: "ca-1" }).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
  });
});
