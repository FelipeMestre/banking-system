import { afterEach, describe, expect, it, vi } from "vitest";
import { authorizedFetch, setAccessTokenGetter, toWebSocketUrl } from "../../../../lib/api/client";

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

describe("authorizedFetch", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("attaches a Bearer header when a token getter is registered", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
    setAccessTokenGetter(async () => "the-access-token");

    await authorizedFetch("http://gateway.example/accounts");

    const [, init] = fetchSpy.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer the-access-token");
  });

  it("omits the Authorization header when no token getter is registered", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));

    await authorizedFetch("http://gateway.example/accounts");

    const [, init] = fetchSpy.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.has("Authorization")).toBe(false);
  });
});
