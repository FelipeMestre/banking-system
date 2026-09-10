import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WithdrawalDialog } from "@/features/withdrawals/components/WithdrawalDialog";
import * as createWithdrawalModule from "@/features/withdrawals/api/create-withdrawal";
import type { Account } from "@/features/accounts/types";

const ACCOUNT: Account = {
  id: "a1",
  account_number: "1111111111111111",
  currency: "USD",
  customer_id: "c1",
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

describe("WithdrawalDialog", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps Accept disabled until an account is selected and a valid amount is entered", () => {
    render(<WithdrawalDialog onClose={vi.fn()} onSuccess={vi.fn()} />);

    const acceptButton = screen.getByRole("button", { name: "Withdraw" });
    expect(acceptButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: "50.00" } });
    expect(acceptButton).toBeDisabled(); // no account selected yet

    fireEvent.click(screen.getByTestId("pick-account"));
    expect(acceptButton).not.toBeDisabled();
  });

  it("keeps Accept disabled for an empty or invalid amount even with an account selected", () => {
    render(<WithdrawalDialog onClose={vi.fn()} onSuccess={vi.fn()} />);
    const acceptButton = screen.getByRole("button", { name: "Withdraw" });

    fireEvent.click(screen.getByTestId("pick-account"));
    expect(acceptButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: "not-a-number" } });
    expect(acceptButton).toBeDisabled();
  });

  it("calls createWithdrawal and onSuccess with the parsed response when approved", async () => {
    const withdrawalResponse = {
      request_id: "r1",
      approved: true,
      amount_applied: 5000,
      new_balance: 5000,
    };
    vi.spyOn(createWithdrawalModule, "createWithdrawal").mockResolvedValue(withdrawalResponse);
    const onSuccess = vi.fn();
    render(<WithdrawalDialog onClose={vi.fn()} onSuccess={onSuccess} />);

    fireEvent.click(screen.getByTestId("pick-account"));
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: "50.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Withdraw" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(withdrawalResponse, ACCOUNT));
  });

  it("shows an inline error and keeps the dialog open when createWithdrawal throws", async () => {
    vi.spyOn(createWithdrawalModule, "createWithdrawal").mockRejectedValue(new Error("account not found"));
    const onClose = vi.fn();
    render(<WithdrawalDialog onClose={onClose} onSuccess={vi.fn()} />);

    fireEvent.click(screen.getByTestId("pick-account"));
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: "50.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Withdraw" }));

    expect(await screen.findByText("account not found")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("shows a decline message, does not call onSuccess, and re-enables Accept on a declined response", async () => {
    vi.spyOn(createWithdrawalModule, "createWithdrawal").mockResolvedValue({
      request_id: "r1",
      approved: false,
      reason: "insufficient_funds",
    });
    const onSuccess = vi.fn();
    const onClose = vi.fn();
    render(<WithdrawalDialog onClose={onClose} onSuccess={onSuccess} />);

    fireEvent.click(screen.getByTestId("pick-account"));
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: "50.00" } });
    const acceptButton = screen.getByRole("button", { name: "Withdraw" });
    fireEvent.click(acceptButton);

    expect(await screen.findByText("Insufficient funds in this account.")).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    await waitFor(() => expect(acceptButton).not.toBeDisabled());
  });
});
