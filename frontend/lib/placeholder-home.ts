/**
 * FAKE DATA — static fixtures for the Home dashboard, with no network path.
 * They exist only so the screen has something to render while the real
 * endpoints (`GET /customers/{id}/accounts`, a transactions read model, a
 * card-summary endpoint) don't exist yet. Nothing here calls `fetch`; do not
 * wire any of this to a live source without replacing it entirely.
 *
 * Values are ported from the bound design's own mock data
 * (design_handoff_openbank_home/OpenBank Home.dc.html) rather than invented,
 * so the screen matches what was actually designed.
 */

import type { Account, Transaction } from "./types";

/** The home page's account summary: the wire `Account` plus a display label
 * the backend has no column for (no `name`/nickname on `accounts` today). */
export type AccountSummary = Account & { label: string };

const SOURCE_ROWS: Record<string, [string, string, string, number, number][]> = {
  "4111000022223333": [
    ["2026-08-24", "Payroll — Meridian Systems", "REF 8841-2290", 1284000, 0],
    ["2026-08-23", "Transfer to Savings ····9014", "REF 8839-1174", 0, 250000],
    ["2026-08-22", "Con Edison — utilities", "DD 4471-0092", 0, 18455],
    ["2026-08-21", "Card settlement ···· 8842", "REF 8830-7741", 0, 91200],
    ["2026-08-20", "Inbound wire — Halvorsen LLC", "SWIFT 22119", 640000, 0],
    ["2026-08-19", "Transfer fee", "REF 8827-0001", 0, 25],
    ["2026-08-18", "Blue Bottle Coffee", "POS 71104", 0, 1840],
    ["2026-08-18", "Refund — Vela Studio", "REF 8821-4408", 12900, 0],
  ],
  "6820441790031188": [
    ["2026-08-25", "SEPA credit — Lindqvist AB", "SEPA 71204", 420000, 0],
    ["2026-08-24", "Deutsche Telekom", "DD 3312-8890", 0, 4990],
    ["2026-08-22", "FX purchase EUR/USD", "REF 8836-2210", 0, 180000],
    ["2026-08-21", "Hotel Adlon Kempinski", "POS 66218", 0, 74500],
    ["2026-08-20", "SEPA credit — Atelier Roux", "SEPA 71188", 96000, 0],
    ["2026-08-19", "Lufthansa City Center", "POS 66102", 0, 38260],
  ],
  "3390117455208841": [
    ["2026-08-26", "Faster Payment — Kelso & Bray", "FP 90114", 310000, 0],
    ["2026-08-25", "HMRC — quarterly VAT", "DD 5520-1140", 0, 428000],
    ["2026-08-24", "Standing order — rent", "SO 4410-2201", 0, 195000],
    ["2026-08-22", "Faster Payment — J. Okafor", "FP 90088", 85000, 0],
    ["2026-08-21", "Waitrose Marylebone", "POS 33017", 0, 9412],
    ["2026-08-20", "Interest credit", "REF 8828-0044", 1877, 0],
  ],
};

export const CUSTOMER_GREETING = "Good afternoon, Helena";
export const LAST_SIGN_IN = "Last sign-in 26 Aug 2026, 09:14 GMT";
export const BALANCES_AS_OF = "26 Aug 2026, 14:02";

export const HOME_ACCOUNTS: AccountSummary[] = [
  {
    id: "acc-fixture-usd-001",
    account_number: "4111000022223333",
    currency: "USD",
    customer_id: "cust-fixture-001",
    branch_id: "branch-fixture-01",
    balance: 4582136,
    status: "active",
    label: "Current account",
  },
  {
    id: "acc-fixture-eur-001",
    account_number: "6820441790031188",
    currency: "EUR",
    customer_id: "cust-fixture-001",
    branch_id: "branch-fixture-01",
    balance: 1897420,
    status: "active",
    label: "Euro account",
  },
  {
    id: "acc-fixture-gbp-001",
    account_number: "3390117455208841",
    currency: "GBP",
    customer_id: "cust-fixture-001",
    branch_id: "branch-fixture-01",
    balance: 2144099,
    status: "active",
    label: "Sterling account",
  },
];

/**
 * Per-account transaction history, newest first, with the running balance
 * pre-computed by walking backwards from the account's current balance —
 * the same derivation the bound design's own mock performs. A real read
 * model would compute this server-side and return `balanceCents` directly
 * (per the design's own note: "In production this must come from the read
 * model, not be derived client-side"); this module is that read model's
 * stand-in until one exists.
 */
export const TRANSACTIONS_BY_ACCOUNT: Record<string, Transaction[]> = Object.fromEntries(
  HOME_ACCOUNTS.map((account) => {
    let running = account.balance;
    const rows = SOURCE_ROWS[account.account_number]?.map(
      ([date, description, reference, creditCents, debitCents], index): Transaction => {
        const balanceCents = running;
        running = running - creditCents + debitCents;
        return {
          id: `${account.account_number}-tx-${index}`,
          date,
          description,
          reference,
          creditCents,
          debitCents,
          balanceCents,
        };
      },
    ) ?? [];
    return [account.account_number, rows];
  }),
);

/** Invented; there is no credit-card entity or endpoint (see the design
 * handoff's "Fidelity" note). Keep this behind a feature flag until one
 * exists — see `SHOW_CREDIT_CARD`. */
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

/**
 * Invented; a design proposal per the handoff, needing an FX rate source and
 * a real card balance before it's real. Kept as a static display only.
 */
export const TOTAL_POSITION = {
  depositsCents: 6841255,
  cardBalanceCents: -358000,
  netCents: 6483255,
  currencySymbol: "£",
  asOf: "26 Aug 2026",
};
