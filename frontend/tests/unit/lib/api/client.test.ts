import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  authorizedFetch,
  describeFailure,
  setAccessTokenGetter,
  toWebSocketUrl,
} from "../../../../lib/api/client";

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

describe("ApiError", () => {
  it("carries the response status alongside the message", () => {
    const error = new ApiError("not found", 404);
    expect(error.message).toBe("not found");
    expect(error.status).toBe(404);
    expect(error).toBeInstanceOf(Error);
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

    const [, init] = fetchSpy.mock.calls[0]!;
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer the-access-token");
  });

  it("omits the Authorization header when no token getter is registered", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));

    await authorizedFetch("http://gateway.example/accounts");

    const [, init] = fetchSpy.mock.calls[0]!;
    const headers = new Headers(init?.headers);
    expect(headers.has("Authorization")).toBe(false);
  });
});

describe("describeFailure", () => {
  it("surfaces a plain FastAPI HTTPException detail on 404", async () => {
    const response = new Response(JSON.stringify({ detail: "account not found" }), { status: 404 });
    expect(await describeFailure(response)).toBe("account not found");
  });

  it("surfaces a plain FastAPI HTTPException detail on 504", async () => {
    const response = new Response(
      JSON.stringify({ detail: "deposit confirmation timeout" }),
      { status: 504 },
    );
    expect(await describeFailure(response)).toBe("deposit confirmation timeout");
  });

  it("prefers the domain error envelope over a detail field when both are present", async () => {
    const response = new Response(
      JSON.stringify({ error: { message: "domain message" }, detail: "should be ignored" }),
      { status: 404 },
    );
    expect(await describeFailure(response)).toBe("domain message");
  });

  it("keeps 401 forced-generic even when a detail field is present", async () => {
    const response = new Response(JSON.stringify({ detail: "should not surface" }), { status: 401 });
    expect(await describeFailure(response)).toBe("Not authenticated. Please log in again.");
  });

  it("keeps 403 forced-generic even when a detail field is present", async () => {
    const response = new Response(JSON.stringify({ detail: "should not surface" }), { status: 403 });
    expect(await describeFailure(response)).toBe("You do not have permission to perform this action.");
  });

  it("falls back to the generic gateway message when there is no detail or error", async () => {
    const response = new Response(JSON.stringify({}), { status: 500 });
    expect(await describeFailure(response)).toMatch(/The gateway answered 500/);
  });

  it("422 stays generic even when a detail field is present (unchanged behavior)", async () => {
    const response = new Response(JSON.stringify({ detail: "some validation detail" }), { status: 422 });
    expect(await describeFailure(response)).toBe(
      "The gateway rejected those values. Check the accounts and amount.",
    );
  });
});
