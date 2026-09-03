/**
 * Fixture accounts for the transfer workspace.
 * TODO: replace with getAccounts() API once the directory endpoint lands.
 * Each entry mirrors the shape the gateway returns for an account, plus a
 * display label the workspace needs. Currencies cover USD/EUR/GBP to exercise
 * the cross-currency warning (AC:06).
 */
export interface TransferAccount {
  id: string;
  account_number: string;
  label: string;
  currency: "USD" | "EUR" | "GBP";
  symbol: string;
  balance: number;
}

export const ACCOUNTS: TransferAccount[] = [
  {
    id: "acc-1",
    account_number: "100000000001",
    label: "Checking ••0001",
    currency: "USD",
    symbol: "$",
    balance: 125000,
  },
  {
    id: "acc-2",
    account_number: "200000000002",
    label: "Savings ••0002",
    currency: "EUR",
    symbol: "€",
    balance: 89000,
  },
  {
    id: "acc-3",
    account_number: "300000000003",
    label: "Travel ••0003",
    currency: "GBP",
    symbol: "£",
    balance: 45000,
  },
];
