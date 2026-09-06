import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CardDetail } from "@/features/credit-cards/components/CardDetail";
import type { UsedCreditEstimate } from "@/features/credit-cards/types";

const ESTIMATE: UsedCreditEstimate = {
  card_account_id: "ca-1", used_credit_estimate: "120.00", credit_limit: "1500.00",
  currency: "USD", is_estimate: true, movement_count: 3,
};

describe("CardDetail", () => {
  it("always shows the approximate label, even right after a fresh purchase", () => {
    render(<CardDetail estimate={ESTIMATE} loading={false} onPay={vi.fn()} />);

    expect(screen.getByText("Used credit (approximate)")).toBeInTheDocument();
    expect(screen.getByText("$120.00")).toBeInTheDocument();
    expect(screen.getByText("of $1500.00")).toBeInTheDocument();
    expect(
      screen.getByText(/may not reflect a purchase or payment made moments ago/),
    ).toBeInTheDocument();
  });

  it("never claims the figure is authoritative or final", () => {
    render(<CardDetail estimate={ESTIMATE} loading={false} onPay={vi.fn()} />);

    expect(screen.queryByText(/authoritative/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/final balance/i)).not.toBeInTheDocument();
  });

  it("calls onPay when the Pay button is clicked", () => {
    const onPay = vi.fn();
    render(<CardDetail estimate={ESTIMATE} loading={false} onPay={onPay} />);

    screen.getByRole("button", { name: "Pay" }).click();

    expect(onPay).toHaveBeenCalledOnce();
  });

  it("shows a loading state while the estimate has not resolved yet", () => {
    render(<CardDetail estimate={null} loading={true} onPay={vi.fn()} />);

    expect(screen.getByText("Loading used credit…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pay" })).not.toBeInTheDocument();
  });
});
