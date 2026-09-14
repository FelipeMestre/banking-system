import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { IssueCardAccountRequest, IssueCardAccountResponse } from "../types";

/** `POST /card-accounts` — issues the card account and its first card
 * atomically; 401 if the caller's Auth0 `sub` is empty. */
export async function issueCardAccount(
  body: IssueCardAccountRequest,
): Promise<IssueCardAccountResponse> {
  const response = await authorizedFetch(`${gatewayOrigin()}/card-accounts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as IssueCardAccountResponse;
}
