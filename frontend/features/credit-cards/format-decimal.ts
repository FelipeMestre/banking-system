/**
 * Formats a backend `Decimal` wire value (a JSON string like `"120.00"`,
 * never integer cents) as currency. Distinct from `lib/money.ts`'s
 * `formatCents`, which is for the accounts/transfers integer-cents
 * convention this feature's amounts do NOT use — `credit_limit`,
 * `used_credit_estimate`, and every `CardMovement.amount` are `Decimal`
 * strings straight off `card_account_dto.py`/`card_usage_dto.py`.
 */
const GROUPING = new Intl.NumberFormat("en-US");

export function formatDecimalCurrency(value: string, symbol: string = "$"): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "—";
  const sign = parsed < 0 ? "-" : "";
  const [whole, fraction = "00"] = Math.abs(parsed).toFixed(2).split(".");
  return `${sign}${symbol}${GROUPING.format(Number(whole))}.${fraction}`;
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

/**
 * Usage as a 0-100 percentage of the limit, for a progress bar. Clamped at
 * both ends: a negative `used` (the customer paid ahead, prepaying the card)
 * reads as 0% used, not a negative bar; `used` exceeding the limit — the
 * live authoritative balance can briefly outrun a limit lowered out of band
 * — clamps at 100%, not an overflowing bar.
 */
export function usagePercent(limit: string, used: number): number {
  const limitCents = creditLimitDecimalToCents(limit);
  if (limitCents === null || limitCents <= 0 || !Number.isFinite(used)) return 0;
  return Math.max(0, Math.min(100, (used / limitCents) * 100));
}

/** "YYYY-MM-DD" -> "MM/YY". String slicing, not `Date` parsing, so this
 * can't drift a month depending on the reader's timezone. */
export function formatExpiry(isoDate: string): string {
  const match = /^(\d{4})-(\d{2})-\d{2}/.exec(isoDate);
  if (!match) return "—";
  const [, year, month] = match;
  return `${month}/${year!.slice(-2)}`;
}
