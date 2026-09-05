/**
 * Formats a backend `Decimal` wire value (a JSON string like `"120.00"`,
 * never integer cents) as currency. Distinct from `lib/money.ts`'s
 * `formatCents`, which is for the accounts/transfers integer-cents
 * convention this feature's amounts do NOT use — `credit_limit`,
 * `used_credit_estimate`, and every `CardMovement.amount` are `Decimal`
 * strings straight off `card_account_dto.py`/`card_usage_dto.py`.
 */
export function formatDecimalCurrency(value: string, symbol: string = "$"): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "—";
  return `${symbol}${parsed.toFixed(2)}`;
}
