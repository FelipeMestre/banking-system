import { authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { TransactionsPage } from "../types";

export async function getTransactions(
  accountNumber: string,
  params: { limit: number; cursor?: string },
): Promise<TransactionsPage> {
  const query = new URLSearchParams({ limit: String(params.limit) });
  if (params.cursor) {
    query.set("cursor", params.cursor);
  }
  const response = await authorizedFetch(
    `${gatewayOrigin()}/accounts/${accountNumber}/transactions?${query}`,
  );
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as TransactionsPage;
}
