import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DepositDialog } from "@/features/deposits/components/DepositDialog";
import * as createDepositModule from "@/features/deposits/api/create-deposit";
import type { Account } from "@/features/accounts/types";

const ACCOUNT: Account = {
  id: "a1",
  account_number: "1111111111111111",
  currency: "USD",
  customer_id: "c1",
  branch_id: "b1",
  balance: 10000,
  status: "active",
};

vi.mock("@/components/shared/AccountPicker", () => ({
  AccountPicker: ({ onSelect }: { onSelect: (account: Account) => void }) => (
    <button type="button" data-testid="pick-account" onClick={() => onSelect(ACCOUNT)}>
      Pick account
    </button>
  ),
}));

describe("DepositDialog", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps Accept disabled until an account is selected and a valid amount is entered", () => {
    render(<DepositDialog onClose={vi.fn()} onSuccess={vi.fn()} />);

    const acceptButton = screen.getByRole("button", { name: "Deposit" });
    expect(acceptButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: "50.00" } });
    expect(acceptButton).toBeDisabled(); // no account selected yet

    fireEvent.click(screen.getByTestId("pick-account"));
    expect(acceptButton).not.toBeDisabled();
  });

  it("keeps Accept disabled for an empty or invalid amount even with an account selected", () => {
    render(<DepositDialog onClose={vi.fn()} onSuccess={vi.fn()} />);
    const acceptButton = screen.getByRole("button", { name: "Deposit" });

    fireEvent.click(screen.getByTestId("pick-account"));
    expect(acceptButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: "not-a-number" } });
    expect(acceptButton).toBeDisabled();
  });

  it("calls createDeposit and onSuccess with the parsed response on submit", async () => {
    const depositResponse = {
      request_id: "r1",
      approved: true,
      amount_applied: 5000,
      new_balance: 15000,
    };
    vi.spyOn(createDepositModule, "createDeposit").mockResolvedValue(depositResponse);
    const onSuccess = vi.fn();
    render(<DepositDialog onClose={vi.fn()} onSuccess={onSuccess} />);

    fireEvent.click(screen.getByTestId("pick-account"));
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: "50.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Deposit" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(depositResponse, ACCOUNT));
  });

  it("shows an inline error and keeps the dialog open when createDeposit throws", async () => {
    vi.spyOn(createDepositModule, "createDeposit").mockRejectedValue(new Error("account not found"));
    const onClose = vi.fn();
    render(<DepositDialog onClose={onClose} onSuccess={vi.fn()} />);

    fireEvent.click(screen.getByTestId("pick-account"));
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: "50.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Deposit" }));

    expect(await screen.findByText("account not found")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });
});
