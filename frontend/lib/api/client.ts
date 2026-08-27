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

export async function describeFailure(response: Response): Promise<string> {
  if (response.status === 422) {
    return "The gateway rejected those values. Check the accounts and amount.";
  }
  return `The gateway answered ${response.status}. Is it running on ${gatewayOrigin()}?`;
}
