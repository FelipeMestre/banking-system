"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatCents } from "@/lib/money";
import { availableCents } from "../format-decimal";
import type { CardAccount } from "../types";

interface Props {
  cardAccount: CardAccount;
  isStale: boolean;
  onPay: () => void;
}

export function CardDetail({ cardAccount, isStale, onPay }: Props) {
  const available = availableCents(cardAccount.credit_limit, cardAccount.used_credit);
  const usedLabel = formatCents(cardAccount.used_credit);
  const availableLabel = available === null ? "—" : formatCents(available);

  return (
    <Card>
      <CardContent className="flex flex-col gap-ds-3">
        <div className="flex items-center justify-between">
          <div className="flex flex-col gap-ds-1">
            <span className="text-xs font-semibold uppercase tracking-[0.08em] text-neutral-600">Used</span>
            <span className="font-heading text-[28px] font-extrabold tracking-[-0.02em] tabular-nums">
              {usedLabel}
            </span>
          </div>
          <div className="flex flex-col items-end gap-ds-1">
            <span className="text-xs font-semibold uppercase tracking-[0.08em] text-neutral-600">Available</span>
            <span className="font-heading text-[28px] font-extrabold tracking-[-0.02em] tabular-nums">
              {availableLabel}
            </span>
          </div>
        </div>
        {isStale ? <Badge variant="secondary">Updating…</Badge> : null}
        <Button type="button" onClick={onPay}>
          Pay
        </Button>
      </CardContent>
    </Card>
  );
}
