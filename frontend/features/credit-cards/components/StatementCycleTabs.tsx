"use client";

import { Download } from "lucide-react";
import { formatCycleLabel } from "../format-date";
import { deriveStatementStatusLabel, type StatementStatusLabel } from "../statement-status";
import type { Statement } from "../types";

interface Props {
  statements: Statement[];
  selectedStatementId: string | null;
  onSelect: (statementId: string) => void;
  onDownload: (statement: Statement) => void;
  downloading: boolean;
}

// Presentation-only rewording for this strip's captions — `statement-status.ts`
// keeps its own canonical wording (asserted verbatim by its unit tests) for
// every other consumer.
const CAPTION: Record<StatementStatusLabel, string> = {
  "Still open": "Current, still open",
  "Paid in full": "Paid in full",
  "Paid minimum, not full": "Paid minimum, not in full",
  "Missed minimum, late fee applied": "Missed minimum — late fee applied",
};

/**
 * Billing-cycle tab strip (`credit-card-monthly-batch-statements`). Each tab
 * is one statement, newest first (as returned by `GET
 * /card-accounts/{id}/statements`) — the newest one is typically still
 * `closed`-not-yet-finalized, which reads as "Current, still open" rather
 * than a closed cycle, so it gets no download button (there's no finalized
 * PDF for a cycle whose payment status isn't decided yet).
 */
export function StatementCycleTabs({
  statements,
  selectedStatementId,
  onSelect,
  onDownload,
  downloading,
}: Props) {
  if (statements.length === 0) {
    return <p className="m-0 text-sm text-neutral-600">No closed billing cycles yet.</p>;
  }

  return (
    <div className="flex flex-wrap items-start gap-x-ds-6 gap-y-ds-2 border-b-2 border-divider">
      {statements.map((statement) => {
        const isSelected = selectedStatementId === statement.id;
        const label = deriveStatementStatusLabel(statement);
        const isOpenCycle = label === "Still open";

        return (
          <div key={statement.id} className="flex items-start gap-ds-2">
            <button
              type="button"
              onClick={() => onSelect(statement.id)}
              aria-current={isSelected ? "true" : undefined}
              className={
                "relative flex flex-col gap-ds-1 px-ds-3 py-ds-2 text-left hover:cursor-pointer " +
                (isSelected ? "bg-neutral-200" : "")
              }
            >
              <span className="font-heading text-sm font-extrabold">
                {formatCycleLabel(statement.period_end)}
              </span>
              <span className="text-xs whitespace-nowrap text-neutral-600">{CAPTION[label]}</span>
              {isSelected ? (
                <span aria-hidden="true" className="absolute inset-x-0 -bottom-[2px] h-[3px] bg-accent" />
              ) : null}
            </button>

            {isOpenCycle ? null : (
              <button
                type="button"
                onClick={() => onDownload(statement)}
                disabled={downloading}
                aria-label={`Download statement for ${formatCycleLabel(statement.period_end)}`}
                className="mt-ds-2 flex size-6 flex-none items-center justify-center border border-divider text-neutral-700 hover:cursor-pointer hover:border-neutral-400 disabled:cursor-default disabled:opacity-50"
              >
                <Download className="size-3.5" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
