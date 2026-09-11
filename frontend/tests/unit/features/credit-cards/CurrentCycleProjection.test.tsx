import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CurrentCycleProjection } from "@/features/credit-cards/components/CurrentCycleProjection";
import type { CurrentCycleProjection as CurrentCycleProjectionData } from "@/features/credit-cards/types";

function makeProjection(overrides: Partial<CurrentCycleProjectionData>): CurrentCycleProjectionData {
  return {
    period_start: "2026-08-21",
    projected_period_end: "2026-09-20",
    overdue_from_previous_cycle: null,
    interest_on_overdue: null,
    new_purchases_this_cycle: "60.00",
    total_to_pay: "60.00",
    payable: true,
    ...overrides,
  };
}

describe("CurrentCycleProjection", () => {
  it("shows new purchases and total to pay, without an overdue line, when absent", () => {
    render(<CurrentCycleProjection projection={makeProjection({})} onPay={vi.fn()} />);

    expect(screen.getAllByText("$60.00")).toHaveLength(2); // new purchases + total, both $60.00
    expect(screen.queryByText("Overdue from previous cycle")).not.toBeInTheDocument();
    expect(screen.queryByText("Interest on overdue")).not.toBeInTheDocument();
  });

  it("renders the overdue and interest lines when present, never as a zero placeholder", () => {
    render(
      <CurrentCycleProjection
        projection={makeProjection({
          overdue_from_previous_cycle: "600.00",
          interest_on_overdue: "12.00",
          new_purchases_this_cycle: "0.00",
          total_to_pay: "612.00",
        })}
        onPay={vi.fn()}
      />,
    );

    expect(screen.getByText("Overdue from previous cycle")).toBeInTheDocument();
    expect(screen.getByText("$600.00")).toBeInTheDocument();
    expect(screen.getByText("Interest on overdue")).toBeInTheDocument();
    expect(screen.getByText("$12.00")).toBeInTheDocument();
    expect(screen.getByText("$612.00")).toBeInTheDocument();
  });

  it("calls onPay when the Pay button is clicked", () => {
    const onPay = vi.fn();
    render(<CurrentCycleProjection projection={makeProjection({})} onPay={onPay} />);

    screen.getByRole("button", { name: "Pay" }).click();

    expect(onPay).toHaveBeenCalledOnce();
  });
});
