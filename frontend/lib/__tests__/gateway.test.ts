import { describe, expect, it } from "vitest";
import { parseTransferStatus, toWebSocketUrl } from "../gateway";

describe("toWebSocketUrl", () => {
  it("maps http to ws and https to wss", () => {
    expect(toWebSocketUrl("http://localhost:8000", "/ws/transfer/abc")).toBe(
      "ws://localhost:8000/ws/transfer/abc",
    );
    expect(toWebSocketUrl("https://gw.example", "/ws/transfer/abc")).toBe(
      "wss://gw.example/ws/transfer/abc",
    );
  });
});

describe("parseTransferStatus", () => {
  it("reads an approved verdict", () => {
    expect(
      parseTransferStatus({ request_id: "r1", status: "approved", account_id: "acc-1", ts: "t" }),
    ).toEqual({ request_id: "r1", status: "approved", account_id: "acc-1", reason: undefined, ts: "t" });
  });

  it("keeps the reason on a decline", () => {
    const parsed = parseTransferStatus({
      request_id: "r1",
      status: "declined",
      reason: "insufficient_funds",
    });
    expect(parsed?.reason).toBe("insufficient_funds");
  });

  it("rejects payloads it does not understand", () => {
    for (const bad of [null, "nope", 7, {}, { request_id: "r1" }, { request_id: "r1", status: "weird" }]) {
      expect(parseTransferStatus(bad)).toBeNull();
    }
  });
});
