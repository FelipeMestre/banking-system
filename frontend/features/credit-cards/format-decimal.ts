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

/**
 * Converts a Decimal string `credit_limit` (e.g. "1,500.00") to integer cents
 * without float arithmetic. Stripping commas and enforcing at most 2 decimals
 * via integer split reuses `lib/money.ts:parseAmountToCents`'s pattern but
 * allows zero and does not clamp — negative or malformed input returns null.
 */
export function creditLimitDecimalToCents(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) return null;
  const stripped = trimmed.replace(/,/g, "");
  if (!/^\d+(\.\d{1,2})?$/.test(stripped)) return null;
  const [wholePart, fracPart = ""] = stripped.split(".");
  const whole = Number(wholePart);
  const frac = fracPart ? Number(fracPart.padEnd(2, "0")) : 0;
  if (!Number.isSafeInteger(whole) || !Number.isSafeInteger(frac)) return null;
  const cents = whole * 100 + frac;
  if (!Number.isSafeInteger(cents)) return null;
  return cents;
}

/**
 * Derived available credit in cents: `limitCents - usedCents`.
 * `used` is authoritative int cents (negative = overpayment, never clamped).
 * Returns null when `limit` is unparseable, so caller can render "—".
 */
export function availableCents(limit: string, used: number): number | null {
  const limitCents = creditLimitDecimalToCents(limit);
  if (limitCents === null) return null;
  if (!Number.isSafeInteger(used)) return null;
  return limitCents - used;
}
