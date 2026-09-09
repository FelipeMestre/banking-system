import { afterEach, describe, expect, it, vi } from "vitest";
import { setAccessTokenGetter } from "@/lib/api/client";
import { runMonthlyClose } from "@/features/cards/api/run-monthly-close";

describe("runMonthlyClose", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("POSTs to /admin/batch/monthly-close and returns the summary", async () => {
    const body = { closed_count: 2, statement_ids: ["s1", "s2"], card_account_ids: ["ca-1", "ca-2"] };
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));

    const result = await runMonthlyClose();

    expect(result).toEqual(body);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(String(url)).toContain("/admin/batch/monthly-close");
    expect(init.method).toBe("POST");
  });

  it("throws an ApiError carrying the response status on failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "boom" } }), { status: 500 }),
    );

    await expect(runMonthlyClose()).rejects.toMatchObject({ status: 500 });
  });
});
