import { currencySymbol, formatCents } from "@/lib/money";
import type { CurrencyTotal } from "@/features/accounts/total-position";

interface Props {
  totals: CurrencyTotal[];
}

/**
 * Total position: one same-currency sum per currency, computed client-side
 * from the already-fetched, customer-scoped accounts list (spec §4.1).
 *
 * Never a single combined figure across currencies — there is no FX rate
 * source in this system, so a multi-currency customer sees each currency's
 * total separately rather than a converted number nobody can vouch for.
 */
export function TotalPosition({ totals }: Props) {
  if (totals.length === 0) {
    return (
      <section>
        <h6 className="mb-[14px] text-xs">Total position</h6>
        <p className="m-0 text-[13px] text-neutral-600">No accounts yet.</p>
      </section>
    );
  }

  return (
    <section>
      <h6 className="mb-[14px] text-xs">Total position</h6>
      <div className="flex flex-col gap-[10px] border-t-2 border-divider pt-[14px] text-[13px] tabular-nums">
        {totals.map(({ currency, totalCents }) => (
          <div key={currency} className="flex justify-between gap-ds-3">
            <span className="text-neutral-700">{currency}</span>
            <span className="font-semibold">{formatCents(totalCents, currencySymbol(currency))}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
