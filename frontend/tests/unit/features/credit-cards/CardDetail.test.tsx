import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CardDetail } from "@/features/credit-cards/components/CardDetail";
import type { CardAccount } from "@/features/credit-cards/types";

const CARD_ACCOUNT: CardAccount = {
  id: "ca-1",
  customer_id: "c1",
  paying_account_id: "a1",
  credit_limit: "500.00",
  status: "active",
  used_credit: 15000,
};

const OVERPAYMENT_ACCOUNT: CardAccount = {
  id: "ca-2",
  customer_id: "c1",
  paying_account_id: "a1",
  credit_limit: "500.00",
  status: "active",
  used_credit: -10000,
};

describe("CardDetail", () => {
  it("renders authoritative Used and Available via formatCents", () => {
    render(<CardDetail cardAccount={CARD_ACCOUNT} isStale={false} onPay={vi.fn()} />);

    expect(screen.getByText("Used")).toBeInTheDocument();
    expect(screen.getByText("$150.00")).toBeInTheDocument();
    expect(screen.getByText("Available")).toBeInTheDocument();
    expect(screen.getByText("$350.00")).toBeInTheDocument();
  });

  it("does not accept UsedCreditEstimate and does not show approximate label", () => {
    render(<CardDetail cardAccount={CARD_ACCOUNT} isStale={false} onPay={vi.fn()} />);

    expect(screen.queryByText(/approximate/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/may not reflect a purchase or payment made moments ago/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/authoritative/i)).not.toBeInTheDocument();
  });

  it("shows Updating… badge when isStale and hides otherwise", () => {
    const { rerender } = render(<CardDetail cardAccount={CARD_ACCOUNT} isStale={true} onPay={vi.fn()} />);
    expect(screen.getByText("Updating…")).toBeInTheDocument();

    rerender(<CardDetail cardAccount={CARD_ACCOUNT} isStale={false} onPay={vi.fn()} />);
    expect(screen.queryByText("Updating…")).not.toBeInTheDocument();
  });

  it("renders overpayment correctly: Used -$100.00 and Available $600.00", () => {
    render(<CardDetail cardAccount={OVERPAYMENT_ACCOUNT} isStale={false} onPay={vi.fn()} />);

    expect(screen.getByText("-$100.00")).toBeInTheDocument();
    expect(screen.getByText("$600.00")).toBeInTheDocument();
  });

  it("renders em dash when credit_limit is unparseable", () => {
    render(
      <CardDetail
        cardAccount={{ ...CARD_ACCOUNT, credit_limit: "not-a-number" }}
        isStale={false}
        onPay={vi.fn()}
      />,
    );
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("calls onPay when Pay button clicked", () => {
    const onPay = vi.fn();
    render(<CardDetail cardAccount={CARD_ACCOUNT} isStale={false} onPay={onPay} />);

    screen.getByRole("button", { name: "Pay" }).click();

    expect(onPay).toHaveBeenCalledOnce();
  });
});
