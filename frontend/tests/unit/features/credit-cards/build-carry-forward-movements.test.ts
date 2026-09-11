import { describe, expect, it } from "vitest";
import { buildCarryForwardMovements } from "@/features/credit-cards/build-carry-forward-movements";
import type { CurrentCycleProjection } from "@/features/credit-cards/types";

function projection(overrides: Partial<CurrentCycleProjection>): CurrentCycleProjection {
  return {
    period_start: "2026-08-18",
    projected_period_end: "2026-09-17",
    overdue_from_previous_cycle: null,
    interest_on_overdue: null,
    new_purchases_this_cycle: "0.00",
    total_to_pay: "0.00",
    payable: true,
    ...overrides,
  };
}

describe("buildCarryForwardMovements", () => {
  it("returns nothing when there is no overdue balance", () => {
    expect(buildCarryForwardMovements(projection({}))).toEqual([]);
  });

  it("returns a carried-balance row and an interest row when both are present", () => {
    const movements = buildCarryForwardMovements(
      projection({ overdue_from_previous_cycle: "48.21", interest_on_overdue: "0.96" }),
    );

    expect(movements).toHaveLength(2);
    expect(movements[0]).toMatchObject({
      movement_type: "carried_balance",
      amount: "48.21",
      occurred_at: "2026-08-18",
    });
    expect(movements[1]).toMatchObject({
      movement_type: "interest",
      amount: "0.96",
      occurred_at: "2026-08-18",
      description: "Interest on overdue balance",
    });
  });

  it("returns only the carried-balance row when interest is absent (e.g. zero-interest edge case)", () => {
    const movements = buildCarryForwardMovements(
      projection({ overdue_from_previous_cycle: "48.21", interest_on_overdue: null }),
    );

    expect(movements).toHaveLength(1);
    expect(movements[0]?.movement_type).toBe("carried_balance");
  });

  it("gives each synthetic row a stable id, distinct from any real movement id", () => {
    const movements = buildCarryForwardMovements(
      projection({ overdue_from_previous_cycle: "48.21", interest_on_overdue: "0.96" }),
    );

    expect(movements.map((m) => m.id)).toEqual(["carried-balance", "carried-balance-interest"]);
  });
});
