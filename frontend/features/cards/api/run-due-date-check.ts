import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";
import type { DueDateCheckRunResult } from "../types";

/**
 * `POST /admin/batch/due-date-check` — admin manual trigger for the same
 * `StatementService.run_due_date_check` the hourly `batch-worker` cron
 * runs, using the gateway's own real current date.
 */
export async function runDueDateCheck(): Promise<DueDateCheckRunResult> {
  const response = await authorizedFetch(`${gatewayOrigin()}/admin/batch/due-date-check`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return (await response.json()) as DueDateCheckRunResult;
}
