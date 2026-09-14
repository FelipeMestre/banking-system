const MONTH_ABBREVIATIONS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/** Parses "YYYY-MM-DD" via string slicing, like `formatExpiry` in
 * `format-decimal.ts` — never `Date`, so this can't drift a day depending on
 * the reader's timezone. */
function parseIsoDate(isoDate: string): { year: string; month: number; day: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate);
  if (!match) return null;
  const [, year, month, day] = match;
  return { year: year!, month: Number(month), day: Number(day) };
}

/** "YYYY-MM-DD" -> "SEP 2026", for a billing cycle's header label. */
export function formatCycleLabel(isoDate: string): string {
  const parsed = parseIsoDate(isoDate);
  if (!parsed) return "—";
  const abbreviation = MONTH_ABBREVIATIONS[parsed.month - 1];
  if (!abbreviation) return "—";
  return `${abbreviation.toUpperCase()} ${parsed.year}`;
}

/** "YYYY-MM-DD" -> "Sep 30, 2026", for a closing or due date value. */
export function formatLongDate(isoDate: string): string {
  const parsed = parseIsoDate(isoDate);
  if (!parsed) return "—";
  const abbreviation = MONTH_ABBREVIATIONS[parsed.month - 1];
  if (!abbreviation) return "—";
  return `${abbreviation} ${parsed.day}, ${parsed.year}`;
}
