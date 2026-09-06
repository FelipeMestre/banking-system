import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { MonthlyCloseRunResult } from "../types";

/**
 * `POST /admin/batch/monthly-close` — admin manual trigger for the same
 * `check_and_close_if_due` sweep the hourly `batch-worker` cron runs, using
 * the gateway's own real current date. No body: this is a trigger, not a
 * date-override tool.
 */
export async function runMonthlyClose(): Promise<MonthlyCloseRunResult> {
  const response = await authorizedFetch(`${gatewayOrigin()}/admin/batch/monthly-close`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as MonthlyCloseRunResult;
}
