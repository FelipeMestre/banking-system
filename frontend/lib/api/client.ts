/**
 * Shared HTTP infrastructure for talking to the FastAPI gateway.
 *
 * The browser talks to the gateway directly (spec §7): it is already the HTTP
 * boundary, so there is no Route Handler or Server Action in between. This is
 * `lib`, not a feature: every feature's API client depends on it, it never
 * depends on them.
 */
const DEFAULT_GATEWAY = "http://localhost:8000";

export function gatewayOrigin(): string {
  return (process.env.NEXT_PUBLIC_GATEWAY_URL ?? DEFAULT_GATEWAY).replace(/\/+$/, "");
}

/**
 * A gateway failure that carries the HTTP status alongside the human-readable
 * message `describeFailure` already produces. A caller that only has a bare
 * `Error` cannot distinguish a 404 (e.g. "no customer linked to this
 * identity") from a 401 or a network failure without parsing the message
 * text — this makes the status a first-class, typed field instead.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function describeFailure(response: Response): Promise<string> {
  if (response.status === 422) {
    return "The gateway rejected those values. Check the accounts and amount.";
  }
  // A domain error (see openbankapi's error_handlers.py) carries a message
  // written for a human — a business rule ("customer still has accounts"),
  // not a status code. Prefer that over the generic fallback whenever it's
  // actually there.
  try {
    const body = await response.json();
    const message = body?.error?.message;
    if (typeof message === "string" && message.length > 0) {
      return message;
    }
  } catch {
    // Not JSON, or no body at all — fall through to the generic message.
  }
  return `The gateway answered ${response.status}. Is it running on ${gatewayOrigin()}?`;
}

/** Turns the gateway's http(s) origin into the matching ws(s) origin. */
export function toWebSocketUrl(origin: string, path: string): string {
  const scheme = origin.startsWith("https://") ? "wss://" : "ws://";
  return `${scheme}${origin.replace(/^https?:\/\//, "")}${path}`;
}

/**
 * Every homepage-backing endpoint requires a Customer resolved via
 * `CurrentCustomerDep` (spec §1.2), which needs a Bearer Access Token.
 *
 * `getAccessTokenSilently()` only exists inside a component tree wrapped by
 * `Auth0Provider` — it is a hook's return value, not something this plain
 * module can call directly. `Auth0ProviderWithNavigate` registers the getter
 * once, on mount, so every plain API-client function can go through
 * `authorizedFetch` without needing to be a hook itself.
 */
type AccessTokenGetter = () => Promise<string | undefined>;

let accessTokenGetter: AccessTokenGetter | null = null;

export function setAccessTokenGetter(getter: AccessTokenGetter | null): void {
  accessTokenGetter = getter;
}

export async function authorizedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = accessTokenGetter ? await accessTokenGetter() : undefined;
  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(input, { ...init, headers });
}
