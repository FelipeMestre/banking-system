/**
 * Invented — a design proposal per the handoff, needing a real card-summary
 * endpoint before it's real. There is no card entity or endpoint in this
 * system today; `SHOW_CREDIT_CARD` gates whether the panel renders at all.
 * Not part of this change's accounts/transactions wiring — kept as a static
 * fixture, same as before, just relocated out of the retired
 * `lib/placeholder-home.ts`.
 */
export const CREDIT_CARD = {
  productName: "Signature",
  maskedNumber: "•••• 8842",
  availableLimitCents: 642000,
  usedCents: 358000,
  totalLimitCents: 1000000,
  currencySymbol: "£",
};

/** Whether the (invented, backend-less) credit card panel renders at all. */
export const SHOW_CREDIT_CARD = true;
