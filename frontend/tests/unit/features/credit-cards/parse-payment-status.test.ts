import { describe, expect, it } from "vitest";
import { parsePaymentStatus } from "@/features/credit-cards/api/parse-payment-status";

describe("parsePaymentStatus", () => {
  it("parses a valid approved status", () => {
    expect(parsePaymentStatus({ request_id: "r1", status: "approved", ts: "2026-09-04T00:00:00Z" })).toEqual({
      request_id: "r1", status: "approved", reason: undefined, ts: "2026-09-04T00:00:00Z",
    });
  });

  it("returns null for an unrecognized status value", () => {
    expect(parsePaymentStatus({ request_id: "r1", status: "unknown" })).toBeNull();
  });

  it("returns null for a non-object payload", () => {
    expect(parsePaymentStatus("not an object")).toBeNull();
  });
});
