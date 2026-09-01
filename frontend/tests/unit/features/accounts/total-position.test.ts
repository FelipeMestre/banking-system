import { describe, expect, it } from "vitest";
import { totalPositionByCurrency } from "../../../../features/accounts/total-position";
import type { Account } from "../../../../features/accounts/types";

function account(overrides: Partial<Account>): Account {
  return {
    id: "id", account_number: "1111111111111111", currency: "USD",
    customer_id: "c1", branch_id: "b1", balance: 0, status: "active",
    ...overrides,
  };
}

describe("totalPositionByCurrency", () => {
  it("sums same-currency accounts into a single total", () => {
    const result = totalPositionByCurrency([
      account({ currency: "USD", balance: 100 }),
      account({ currency: "USD", balance: 250 }),
    ]);

    expect(result).toEqual([{ currency: "USD", totalCents: 350 }]);
  });

  it("keeps different currencies as separate sums, never combined", () => {
    const result = totalPositionByCurrency([
      account({ currency: "USD", balance: 100 }),
      account({ currency: "EUR", balance: 200 }),
    ]);

    expect(result).toEqual(
      expect.arrayContaining([
        { currency: "USD", totalCents: 100 },
        { currency: "EUR", totalCents: 200 },
      ]),
    );
    expect(result).toHaveLength(2);
  });

  it("returns an empty list for no accounts", () => {
    expect(totalPositionByCurrency([])).toEqual([]);
  });
});
