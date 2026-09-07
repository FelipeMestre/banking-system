import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SimulatePurchaseDialog } from "@/features/cards/components/SimulatePurchaseDialog";
import * as cardsModule from "@/features/cards/api/get-cards";
import * as requestPurchaseModule from "@/features/cards/api/request-purchase";
import * as watchModule from "@/features/cards/api/watch-purchase-status";
import type { CardListItem } from "@/features/cards/types";

const CARDS: CardListItem[] = [
  { id: "card-1", card_account_id: "ca-1", card_number: "4111111111111111", status: "active", customer_name: "Alex Morgan" },
];

describe("SimulatePurchaseDialog", () => {
  // jsdom doesn't implement scrollIntoView; Radix Select's option-highlight
  // effect calls it on open.
  Element.prototype.scrollIntoView = vi.fn();

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a single Close button once the purchase resolves, not a Cancel and a Close saying the same thing", async () => {
    vi.spyOn(cardsModule, "getCards").mockResolvedValue({ items: CARDS, total: 1, limit: 100, offset: 0 });
    vi.spyOn(requestPurchaseModule, "requestPurchase").mockResolvedValue({
      request_id: "r1", status: "pending",
    });
    vi.spyOn(watchModule, "watchPurchaseStatus").mockImplementation(() => () => {});

    render(<SimulatePurchaseDialog onClose={vi.fn()} />);

    await screen.findByRole("combobox", { name: "Card" });
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("combobox", { name: "Card" }));
    fireEvent.click(await screen.findByText("Alex Morgan — •••• 1111 · active"));
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "49.99" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit purchase" }));

    await waitFor(() => expect(requestPurchaseModule.requestPurchase).toHaveBeenCalled());

    // The dialog's own "X" icon button is separately aria-labeled "Close" —
    // scope to the visible text so this only counts the footer buttons.
    expect(await screen.findByText("Close")).toBeInTheDocument();
    expect(screen.getAllByText("Close")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });
});
