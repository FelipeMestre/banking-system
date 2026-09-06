"use client";

import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { deriveStatementStatusLabel, statementStatusBadgeVariant } from "../statement-status";
import type { Statement } from "../types";

interface Props {
  statements: Statement[];
  selectedStatementId: string | null;
  onSelect: (statementId: string) => void;
}

/**
 * Billing-cycle tab strip (`credit-card-monthly-batch-statements`). Each tab
 * is one closed statement, newest first (as returned by `GET
 * /card-accounts/{id}/statements`); the status label is derived, never taken
 * verbatim from the raw `status` field — see `deriveStatementStatusLabel`.
 */
export function StatementCycleTabs({ statements, selectedStatementId, onSelect }: Props) {
  if (statements.length === 0) {
    return <p className="m-0 text-sm text-neutral-600">No closed billing cycles yet.</p>;
  }

  return (
    <Tabs value={selectedStatementId ?? statements[0]?.id} onValueChange={onSelect}>
      <TabsList variant="line" className="w-full flex-wrap justify-start overflow-x-auto">
        {statements.map((statement) => {
          const label = deriveStatementStatusLabel(statement);
          return (
            <TabsTrigger key={statement.id} value={statement.id} className="flex-col gap-1 py-2">
              <span className="text-xs font-semibold">{statement.period_end}</span>
              <Badge variant={statementStatusBadgeVariant(label)} className="text-[10px]">
                {label}
              </Badge>
            </TabsTrigger>
          );
        })}
      </TabsList>
    </Tabs>
  );
}
