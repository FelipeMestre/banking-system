import { describe, expect, it } from "vitest";
import { toWebSocketUrl } from "../../../../lib/api/client";

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
