import type { Account } from "./types";

export interface CurrencyTotal {
  currency: string;
  totalCents: number;
}

/**
 * Same-currency sum, never combined across currencies (spec §4.1).
 *
 * No FX rate source exists in this system, so a multi-currency customer sees
 * one total per currency rather than a single converted figure — combining
 * them would require inventing a conversion rate this architecture has
 * nowhere to source honestly.
 */
export function totalPositionByCurrency(accounts: Account[]): CurrencyTotal[] {
  const totals = new Map<string, number>();
  for (const account of accounts) {
    totals.set(account.currency, (totals.get(account.currency) ?? 0) + account.balance);
  }
  return Array.from(totals, ([currency, totalCents]) => ({ currency, totalCents }));
}
