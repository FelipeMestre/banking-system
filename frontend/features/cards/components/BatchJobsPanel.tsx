"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { runDueDateCheck } from "../api/run-due-date-check";
import { runMonthlyClose } from "../api/run-monthly-close";
import type { DueDateCheckRunResult, MonthlyCloseRunResult } from "../types";

type RunState<TResult> =
  | { kind: "idle" }
  | { kind: "pending" }
  | { kind: "done"; result: TResult }
  | { kind: "error"; message: string };

interface JobProps<TResult> {
  label: string;
  pendingLabel: string;
  run: () => Promise<TResult>;
  describeResult: (result: TResult) => string;
}

/**
 * One admin batch-trigger button: runs `run()`, then shows its outcome
 * inline (never fire-and-forget) — mirrors `SimulatePurchaseButton`'s
 * directness (no confirmation dialog needed, this is an admin testing
 * tool), but reports the result as text instead of opening a popup, since
 * there is no input to collect first.
 */
function BatchJobButton<TResult>({ label, pendingLabel, run, describeResult }: JobProps<TResult>) {
  const [state, setState] = useState<RunState<TResult>>({ kind: "idle" });

  function handleClick() {
    setState({ kind: "pending" });
    run()
      .then((result) => setState({ kind: "done", result }))
      .catch((caught: unknown) => {
        setState({
          kind: "error",
          message: caught instanceof Error ? caught.message : "The job did not complete.",
        });
      });
  }

  return (
    <div className="flex flex-col gap-ds-2">
      <Button
        type="button"
        variant="outline"
        onClick={handleClick}
        disabled={state.kind === "pending"}
      >
        {state.kind === "pending" ? pendingLabel : label}
      </Button>
      {state.kind === "done" ? (
        <p className="m-0 text-xs text-neutral-600">{describeResult(state.result)}</p>
      ) : state.kind === "error" ? (
        <ErrorMessage message={state.message} />
      ) : null}
    </div>
  );
}

/**
 * Admin-only testing panel (Credit Cards Phase 4): manually runs the two
 * jobs the hourly `batch-worker` cron otherwise only runs on its own
 * schedule — `POST /admin/batch/monthly-close` and
 * `POST /admin/batch/due-date-check`. Both call the REAL batch logic with
 * the gateway's own current date; this only exists so an admin can test the
 * monthly-close/due-date/late-fee flow without waiting for the cron or
 * faking server time.
 */
export function BatchJobsPanel() {
  return (
    <div className="flex flex-wrap gap-ds-4">
      <BatchJobButton<MonthlyCloseRunResult>
        label="Run monthly close check"
        pendingLabel="Running…"
        run={runMonthlyClose}
        describeResult={(result) =>
          result.closed_count === 0
            ? "No account was due to close."
            : `Closed ${result.closed_count} statement${result.closed_count === 1 ? "" : "s"}.`
        }
      />
      <BatchJobButton<DueDateCheckRunResult>
        label="Run due-date check"
        pendingLabel="Running…"
        run={runDueDateCheck}
        describeResult={(result) =>
          result.finalized_count === 0
            ? "No statement had a due date today."
            : `Finalized ${result.finalized_count} statement${result.finalized_count === 1 ? "" : "s"}` +
              (result.late_fees_applied_count > 0
                ? `, applied ${result.late_fees_applied_count} late fee${result.late_fees_applied_count === 1 ? "" : "s"}.`
                : ".")
        }
      />
    </div>
  );
}
