/** Amounts are integer cents end to end (spec §4), so never convert via floats. */

const GROUPING = new Intl.NumberFormat("en-US");

/**
 * Formats integer cents as currency using integer arithmetic only.
 *
 * Dividing by 100 to format would introduce a binary rounding error on exactly
 * the values a ledger cares about, so the whole and fractional parts are split
 * with integer division instead.
 *
 * `symbol` defaults to "$" so every existing single-currency call site is
 * unchanged; the home page's multi-currency accounts pass their own symbol
 * (€, £, ...). This does no locale-aware currency formatting beyond that
 * prefix — grouping stays en-US regardless of currency, matching the bound
 * design, which does the same.
 */
export function formatCents(cents: number, symbol: string = "$"): string {
  if (!Number.isFinite(cents)) return "—";
  const rounded = Math.trunc(cents);
  const sign = rounded < 0 ? "-" : "";
  const absolute = Math.abs(rounded);
  const whole = Math.trunc(absolute / 100);
  const fraction = absolute % 100;
  return `${sign}${symbol}${GROUPING.format(whole)}.${String(fraction).padStart(2, "0")}`;
}

/**
 * Masks an account number down to its trailing 4 characters for display.
 *
 * This is total, not just the 16-digit happy path: an account number is
 * still sensitive even if malformed, so any input caps exposure to at most
 * 4 trailing characters and never throws.
 *
 * The space between the dots and the digits ("•••• 3456", not "••••3456")
 * is a design requirement, not a stylistic choice on this end — it's the
 * literal string the bound design renders, so it lives in the shared
 * formatter rather than each caller re-joining the pieces itself.
 */
export function maskAccountNumber(accountNumber: string): string {
  const lastFour = accountNumber.slice(-4);
  return `•••• ${lastFour}`;
}

/**
 * Groups a revealed account number into 4-digit chunks separated by a dash
 * (e.g. "1111222233334444" -> "1111-2222-3333-4444"), for readability.
 *
 * Purely a display grouping — this only runs on the already-revealed number,
 * never the masked placeholder, and the raw ungrouped value is what actually
 * gets copied to the clipboard, not this formatted string.
 *
 * Total like `maskAccountNumber`: a trailing partial group (anything not a
 * multiple of 4 characters) is kept as-is rather than dropped, so this never
 * throws or silently truncates a malformed value.
 */
export function formatAccountNumber(accountNumber: string): string {
  return accountNumber.replace(/(.{4})(?=.)/g, "$1-");
}

const CURRENCY_SYMBOLS: Record<string, string> = { USD: "$", EUR: "€", GBP: "£" };

/**
 * The display symbol for an ISO 4217 currency code. Falls back to the code
 * itself for anything not in the small set this app's accounts actually use,
 * rather than throwing on a currency nobody has wired up yet.
 */
export function currencySymbol(currencyCode: string): string {
  return CURRENCY_SYMBOLS[currencyCode] ?? currencyCode;
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

/**
 * Parses a human decimal amount (e.g. "1,250.00") into integer cents without
 * using floats. Returns null for anything not a positive amount with at most
 * two decimal places.
 */
export function parseAmountToCents(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed.length === 0) return null;
  const stripped = trimmed.replace(/,/g, "");
  if (!/^\d+(\.\d{1,2})?$/.test(stripped)) return null;
  const [wholePart, fracPart = ""] = stripped.split(".");
  const whole = Number(wholePart);
  const frac = fracPart ? Number(fracPart.padEnd(2, "0")) : 0;
  if (!Number.isSafeInteger(whole) || !Number.isSafeInteger(frac)) return null;
  const cents = whole * 100 + frac;
  if (!Number.isSafeInteger(cents) || cents <= 0) return null;
  return cents;
}
