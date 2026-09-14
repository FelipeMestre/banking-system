/**
 * Validates a decimal purchase amount (e.g. "49.99") the same shape the
 * backend's `PurchaseRequestDTO.amount` accepts (`Decimal, gt=0` — see
 * openbankapi/api/v1/dtos/purchase_dto.py). This is deliberately not
 * `lib/money.ts`'s cents-based parsing: transfers move integer cents, but a
 * purchase's `amount` field is the decimal value in the purchase's own
 * currency, sent as-is for the gateway to convert.
 *
 * Returns the trimmed string to send verbatim, or null when invalid.
 */
export function parsePurchaseAmount(raw: string): string | null {
  const trimmed = raw.trim();
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return null;
  if (Number(trimmed) <= 0) return null;
  return trimmed;
}
