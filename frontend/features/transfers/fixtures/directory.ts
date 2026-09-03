/**
 * Fixture directory for recipient preview.
 * TODO: replace with directory API (keyed map or search endpoint) once available.
 * Each entry is a known recipient account that the ToAccountField can preview
 * when the user types ≥6 digits. Includes the failing number 7723490011 for
 * the gated mock simulation (AC:07).
 */
export interface DirectoryEntry {
  account_number: string;
  first: string;
  last: string;
  name: string;
  currency: string;
  initials: string;
}

export const DIRECTORY: DirectoryEntry[] = [
  {
    account_number: "7723490011",
    first: "Alex",
    last: "Morgan",
    name: "Alex Morgan",
    currency: "USD",
    initials: "AM",
  },
  {
    account_number: "8800001122",
    first: "Sofia",
    last: "Rossi",
    name: "Sofia Rossi",
    currency: "EUR",
    initials: "SR",
  },
  {
    account_number: "9900003344",
    first: "James",
    last: "Patel",
    name: "James Patel",
    currency: "GBP",
    initials: "JP",
  },
];
