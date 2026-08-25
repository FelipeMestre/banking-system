/** Amounts are integer cents end to end (spec §4), so never convert via floats. */

const GROUPING = new Intl.NumberFormat("en-US");

/**
 * Formats integer cents as currency using integer arithmetic only.
 *
 * Dividing by 100 to format would introduce a binary rounding error on exactly
 * the values a ledger cares about, so the whole and fractional parts are split
 * with integer division instead.
 */
export function formatCents(cents: number): string {
  if (!Number.isFinite(cents)) return "—";
  const rounded = Math.trunc(cents);
  const sign = rounded < 0 ? "-" : "";
  const absolute = Math.abs(rounded);
  const whole = Math.trunc(absolute / 100);
  const fraction = absolute % 100;
  return `${sign}$${GROUPING.format(whole)}.${String(fraction).padStart(2, "0")}`;
}

/**
 * Reads the amount field. Returns null for anything that is not a positive
 * whole number of cents, which is exactly what the gateway will accept.
 */
export function parseCentsInput(raw: string): number | null {
  const trimmed = raw.trim();
  if (!/^\d+$/.test(trimmed)) return null;
  const cents = Number(trimmed);
  if (!Number.isSafeInteger(cents) || cents <= 0) return null;
  return cents;
}
