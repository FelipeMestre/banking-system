import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CardList } from "@/features/credit-cards/components/CardList";
import * as cardAccountsModule from "@/features/credit-cards/api/get-card-accounts";
import * as usedCreditModule from "@/features/credit-cards/api/get-used-credit";
import type { CardAccountListItem } from "@/features/credit-cards/types";

const TWO_CARDS: CardAccountListItem[] = [
  {
    card_account: { id: "ca-1", customer_id: "c1", paying_account_id: "a1", credit_limit: "500.00", status: "active", used_credit: 15000 },
    card: { id: "card-1", card_account_id: "ca-1", card_number: "•••• •••• •••• 1234", expiration_date: "2029-01-01", status: "active" },
  },
  {
    card_account: { id: "ca-2", customer_id: "c1", paying_account_id: "a1", credit_limit: "500.00", status: "blocked", used_credit: 0 },
    card: { id: "card-2", card_account_id: "ca-2", card_number: "•••• •••• •••• 5678", expiration_date: "2027-06-01", status: "blocked" },
  },
];

describe("CardList", () => {
  it("renders both cards with masked number, status label, expiration, and used/limit figures", () => {
    render(<CardList items={TWO_CARDS} selectedCardAccountId={null} onSelect={vi.fn()} />);

    expect(screen.getByText("•••• •••• •••• 1234")).toBeInTheDocument();
    expect(screen.getByText("•••• •••• •••• 5678")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Blocked")).toBeInTheDocument();
    expect(screen.getByText("Exp 01/29")).toBeInTheDocument();
    expect(screen.getByText("Exp 06/27")).toBeInTheDocument();
    expect(screen.getByText("$150.00")).toBeInTheDocument();
    expect(screen.getAllByText("used of $500.00")).toHaveLength(2);
  });

  it("does not issue extra per-card fetches when rendering N items", () => {
    const cardAccountsSpy = vi.spyOn(cardAccountsModule, "getCardAccounts");
    const usedCreditSpy = vi.spyOn(usedCreditModule, "getUsedCredit");

    render(<CardList items={TWO_CARDS} selectedCardAccountId={null} onSelect={vi.fn()} />);

    expect(cardAccountsSpy).not.toHaveBeenCalled();
    expect(usedCreditSpy).not.toHaveBeenCalled();
  });

  it("calls onSelect with the clicked card account's id", () => {
    const onSelect = vi.fn();
    render(<CardList items={TWO_CARDS} selectedCardAccountId={null} onSelect={onSelect} />);

    screen.getByText("•••• •••• •••• 5678").closest("button")!.click();

    expect(onSelect).toHaveBeenCalledWith("ca-2");
  });

  it("renders an empty state when the customer has no cards", () => {
    render(<CardList items={[]} selectedCardAccountId={null} onSelect={vi.fn()} />);

    expect(screen.getByText("You have no credit cards yet.")).toBeInTheDocument();
  });

  it("marks the selected card with a top accent bar, not a full border highlight", () => {
    render(<CardList items={TWO_CARDS} selectedCardAccountId="ca-1" onSelect={vi.fn()} />);

    const selectedButton = screen.getByText("•••• •••• •••• 1234").closest("button")!;
    const unselectedButton = screen.getByText("•••• •••• •••• 5678").closest("button")!;

    expect(selectedButton.getAttribute("aria-current")).toBe("true");
    expect(selectedButton.querySelector('[aria-hidden="true"]')?.className).toContain("bg-accent");
    expect(unselectedButton.querySelector('[aria-hidden="true"]')?.className).toContain("bg-transparent");
  });

  it("shows a 0% usage bar when used_credit is negative — a prepaid card, not a negative bar", () => {
    const prepaidCard: CardAccountListItem[] = [
      {
        card_account: { id: "ca-3", customer_id: "c1", paying_account_id: "a1", credit_limit: "500.00", status: "active", used_credit: -2000 },
        card: { id: "card-3", card_account_id: "ca-3", card_number: "•••• •••• •••• 9999", expiration_date: "2028-01-01", status: "active" },
      },
    ];

    render(<CardList items={prepaidCard} selectedCardAccountId={null} onSelect={vi.fn()} />);

    const bar = screen.getByText("•••• •••• •••• 9999").closest("button")!.querySelector(".bg-neutral-300 > div") as HTMLElement;
    expect(bar.style.width).toBe("0%");
  });

  it("shows a proportional usage bar for a normal balance", () => {
    render(<CardList items={TWO_CARDS} selectedCardAccountId={null} onSelect={vi.fn()} />);

    const bar = screen.getByText("•••• •••• •••• 1234").closest("button")!.querySelector(".bg-neutral-300 > div") as HTMLElement;
    // used_credit 15000 (=$150.00) of a $500.00 limit -> 30%.
    expect(bar.style.width).toBe("30%");
  });
});
