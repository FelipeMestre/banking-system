import { CreditCard } from "lucide-react";
import { formatCents } from "@/lib/money";
import type { CREDIT_CARD } from "./credit-card-fixture";
import { DS_ICON_PROPS } from "@/lib/icon-props";

interface Props {
  card: typeof CREDIT_CARD;
}

/**
 * Invented — there is no credit-card entity or endpoint (see the design
 * handoff's "Fidelity" note). `SHOW_CREDIT_CARD` gates whether this renders
 * at all; treat it as the real feature flag once a card API exists.
 */
export function CreditCardPanel({ card }: Props) {
  const utilisationPercent = Math.round((card.usedCents / card.totalLimitCents) * 100);

  return (
    <section>
      <h6 className="mb-[14px] text-xs">Credit card</h6>
      <div className="flex flex-col gap-[18px] border-2 border-divider p-[20px]">
        <div className="flex items-start justify-between gap-ds-3">
          <div className="flex h-[36px] w-[54px] flex-none items-center justify-center bg-text text-bg">
            <CreditCard size={26} {...DS_ICON_PROPS} />
          </div>
          <div className="text-right">
            <div className="font-body text-[11px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
              {card.productName}
            </div>
            <div className="mt-[4px] text-xs tracking-[0.06em] text-neutral-600 tabular-nums">
              {card.maskedNumber}
            </div>
          </div>
        </div>

        <div>
          <div className="mb-ds-2 font-body text-[10px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
            Available limit
          </div>
          <div className="flex items-baseline gap-[5px]">
            <span className="font-heading text-[15px] font-extrabold text-neutral-700">
              {card.currencySymbol}
            </span>
            <span className="font-heading text-[32px] font-extrabold leading-none tracking-[-0.03em] tabular-nums">
              {formatCents(card.availableLimitCents, "")}
            </span>
          </div>
        </div>

        <div className="h-[2px] bg-neutral-300">
          <div className="h-[2px] bg-accent" style={{ width: `${utilisationPercent}%` }} />
        </div>

        <div className="flex items-center justify-between text-xs text-neutral-600 tabular-nums">
          <span>{formatCents(card.usedCents, card.currencySymbol)} used</span>
          <span>of {formatCents(card.totalLimitCents, card.currencySymbol)}</span>
        </div>
      </div>
    </section>
  );
}
