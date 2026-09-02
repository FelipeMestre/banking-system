import { authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { Account, FirstAccountKyc } from "../types";

/**
 * Self-service first-account creation (`POST /accounts/me`). Currency and
 * branch are always resolved server-side (spec — zero client-supplied
 * account params), so there is nothing here for a caller to get wrong there.
 *
 * `kyc` is only ever needed when auto-linking a never-before-seen Auth0
 * identity (amendment) — omitted (the already-shipped, unchanged behavior),
 * the request body stays `{}`.
 */
export async function createAccount(kyc?: FirstAccountKyc): Promise<Account> {
  const response = await authorizedFetch(`${gatewayOrigin()}/accounts/me`, {
    method: "POST",
    headers: kyc ? { "Content-Type": "application/json" } : undefined,
    body: kyc ? JSON.stringify(kyc) : undefined,
  });
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as Account;
}
