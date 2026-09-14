import { afterEach, describe, expect, it, vi } from "vitest";
import { setAccessTokenGetter } from "@/lib/api/client";
import { runDueDateCheck } from "@/features/cards/api/run-due-date-check";

describe("runDueDateCheck", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("POSTs to /admin/batch/due-date-check and returns the summary", async () => {
    const body = { finalized_count: 3, late_fees_applied_count: 1 };
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));

    const result = await runDueDateCheck();

    expect(result).toEqual(body);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(String(url)).toContain("/admin/batch/due-date-check");
    expect(init.method).toBe("POST");
  });

  it("throws an ApiError carrying the response status on failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "boom" } }), { status: 500 }),
    );

    await expect(runDueDateCheck()).rejects.toMatchObject({ status: 500 });
  });
});
