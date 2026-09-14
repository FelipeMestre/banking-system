import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QuickActions } from "@/components/home/QuickActions";
import * as customerModule from "@/features/credit-cards/api/get-current-customer";
import * as cardAccountsModule from "@/features/credit-cards/api/get-card-accounts";

describe("QuickActions", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("Send a transfer and Pay a bill are both live; Download statement stays disabled", () => {
    render(<QuickActions />);

    expect(screen.getByRole("link", { name: "Send a transfer" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pay a bill" })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: "Download statement" })).toBeDisabled();
  });

  it("opens the Pay a bill dialog on click", async () => {
    vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
    vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue({
      items: [], total: 0, limit: 50, offset: 0,
    });

    render(<QuickActions />);
    fireEvent.click(screen.getByRole("button", { name: "Pay a bill" }));

    expect(await screen.findByRole("heading", { name: "Pay a bill" })).toBeInTheDocument();
  });
});
