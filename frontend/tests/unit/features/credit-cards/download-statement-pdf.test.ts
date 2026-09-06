import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, setAccessTokenGetter } from "@/lib/api/client";
import {
  downloadStatementPdf,
  fetchStatementPdf,
  triggerBrowserDownload,
} from "@/features/credit-cards/api/download-statement-pdf";

describe("fetchStatementPdf", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("requests the PDF endpoint and returns a Blob", async () => {
    const pdfBytes = new Uint8Array([0x25, 0x50, 0x44, 0x46]); // "%PDF"
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(pdfBytes, { status: 200, headers: { "content-type": "application/pdf" } }),
    );

    const blob = await fetchStatementPdf("ca-1", "st-1");

    expect(blob.size).toBe(4);
    const requestedUrl = fetchSpy.mock.calls[0]?.[0] as string;
    expect(requestedUrl).toContain("/card-accounts/ca-1/statements/st-1/pdf");
  });

  it("throws an ApiError carrying the response status on failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "not found" } }), { status: 404 }),
    );

    const error = await fetchStatementPdf("ca-1", "st-1").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
  });
});

describe("triggerBrowserDownload", () => {
  beforeEach(() => {
    if (!URL.createObjectURL) {
      URL.createObjectURL = vi.fn(() => "blob:mock-url");
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = vi.fn();
    }
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-url");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates and clicks a throwaway anchor with the given filename", () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const blob = new Blob([new Uint8Array([1, 2, 3])], { type: "application/pdf" });

    triggerBrowserDownload(blob, "statement-2026-08-20.pdf");

    expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
    expect(clickSpy).toHaveBeenCalledOnce();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
  });
});

describe("downloadStatementPdf", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("fetches then triggers a browser download", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(new Uint8Array([0x25, 0x50, 0x44, 0x46]), { status: 200 }),
    );
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-url");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    await downloadStatementPdf("ca-1", "st-1", "statement.pdf");

    expect(clickSpy).toHaveBeenCalledOnce();
  });
});
