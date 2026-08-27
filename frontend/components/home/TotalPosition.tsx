import { formatCents } from "@/lib/money";
import type { TOTAL_POSITION } from "@/lib/placeholder-home";

interface Props {
  position: typeof TOTAL_POSITION;
}

/** U+2212 minus, not a hyphen — matches the design's own negative-amount
 * glyph for this one section. Local to this component: the shared
 * `formatCents` keeps its own, different, already-tested hyphen convention
 * for the rest of the app, and this isn't a general rule worth changing it
 * for. */
function signedAmount(cents: number, symbol: string): string {
  return cents < 0 ? `−${formatCents(-cents, symbol)}` : formatCents(cents, symbol);
}

/**
 * Invented — a design proposal per the handoff, needing an FX rate source
 * and a real card balance before it's real. Static display only.
 */
export function TotalPosition({ position }: Props) {
  const { depositsCents, cardBalanceCents, netCents, currencySymbol, asOf } = position;

  return (
    <section>
      <h6 className="mb-[14px] text-xs">Total position</h6>
      <div className="flex flex-col gap-[10px] border-t-2 border-divider pt-[14px] text-[13px] tabular-nums">
        <div className="flex justify-between gap-ds-3">
          <span className="text-neutral-700">Deposits</span>
          <span className="font-semibold">{formatCents(depositsCents, currencySymbol)}</span>
        </div>
        <div className="flex justify-between gap-ds-3">
          <span className="text-neutral-700">Card balance</span>
          <span className="font-semibold">{signedAmount(cardBalanceCents, currencySymbol)}</span>
        </div>
        <div className="flex justify-between gap-ds-3 border-t border-neutral-300 pt-[10px]">
          <span className="text-neutral-700">Net</span>
          <span className="font-heading text-[16px] font-extrabold">
            {signedAmount(netCents, currencySymbol)}
          </span>
        </div>
        <div className="text-[10px] tracking-[0.04em] text-neutral-600">
          Converted at ECB reference rates, {asOf}.
        </div>
      </div>
    </section>
  );
}
