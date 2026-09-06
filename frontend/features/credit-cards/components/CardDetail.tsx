"use client";

import { Button } from "@/components/ui/button";
import { formatDecimalCurrency } from "../format-decimal";
import type { UsedCreditEstimate } from "../types";

interface Props {
  estimate: UsedCreditEstimate | null;
  loading: boolean;
  onPay: () => void;
}

/**
 * Shows the derived used-credit approximation. The "approximate" label is
 * NOT conditional on anything — it must always be present, including
 * immediately after a fresh purchase (spec: "Race window is documented, not
 * hidden"), since this value can never be claimed authoritative or final.
 */
export function CardDetail({ estimate, loading, onPay }: Props) {
  return (
    <section className="flex flex-col gap-ds-3 border-2 border-divider p-ds-4">
      {loading || estimate === null ? (
        <p className="m-0 text-sm text-neutral-600">Loading used credit…</p>
      ) : (
        <>
          <div>
            <div className="mb-ds-1 font-body text-[10px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
              Used credit (approximate)
            </div>
            <div className="flex items-baseline gap-ds-2">
              <span className="font-heading text-[28px] font-extrabold tracking-[-0.02em] tabular-nums">
                {formatDecimalCurrency(estimate.used_credit_estimate)}
              </span>
              <span className="text-sm text-neutral-600">
                of {formatDecimalCurrency(estimate.credit_limit)}
              </span>
            </div>
            <p className="m-0 mt-ds-1 text-xs text-neutral-600">
              This is an approximate figure derived from recent activity — it may not reflect a
              purchase or payment made moments ago.
            </p>
          </div>
          <Button type="button" onClick={onPay}>
            Pay
          </Button>
        </>
      )}
    </section>
  );
}
