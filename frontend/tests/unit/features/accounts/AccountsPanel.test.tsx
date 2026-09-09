import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountsPanel } from "@/features/accounts/components/AccountsPanel";
import { usePermissions } from "@/lib/auth/usePermissions";
import type { Account } from "@/features/accounts/types";
import type { DepositResponse } from "@/features/deposits";
import type { WithdrawalResponse } from "@/features/withdrawals";

const ACCOUNT: Account = {
  id: "a1",
  account_number: "1111111111111111",
  currency: "USD",
  customer_id: "c1",
  branch_id: "b1",
  balance: 10000,
  status: "active",
};

vi.mock("@/lib/auth/usePermissions", () => ({
  usePermissions: vi.fn(),
}));

vi.mock("@/features/accounts/components/AccountsList", () => ({
  AccountsList: ({ refreshToken }: { refreshToken?: number }) => (
    <div data-testid="accounts-list" data-refresh-token={refreshToken}>
      Accounts
    </div>
  ),
}));

let capturedOnSuccess: ((response: DepositResponse, account: Account) => void) | null = null;
let capturedWithdrawOnSuccess: ((response: WithdrawalResponse, account: Account) => void) | null = null;

vi.mock("@/features/deposits", () => ({
  DepositDialog: ({
    onSuccess,
  }: {
    onClose: () => void;
    onSuccess: (response: DepositResponse, account: Account) => void;
  }) => {
    capturedOnSuccess = onSuccess;
    return <div data-testid="deposit-dialog">Deposit dialog</div>;
  },
}));

vi.mock("@/features/withdrawals", () => ({
  WithdrawalDialog: ({
    onSuccess,
  }: {
    onClose: () => void;
    onSuccess: (response: WithdrawalResponse, account: Account) => void;
  }) => {
    capturedWithdrawOnSuccess = onSuccess;
    return <div data-testid="withdrawal-dialog">Withdrawal dialog</div>;
  },
}));

const mockedUsePermissions = vi.mocked(usePermissions);

describe("AccountsPanel", () => {
  afterEach(() => {
    vi.clearAllMocks();
    capturedOnSuccess = null;
    capturedWithdrawOnSuccess = null;
  });

  it("does not render the Deposit or Withdraw buttons without write:admin", () => {
    mockedUsePermissions.mockReturnValue({
      hasReadAdmin: true,
      hasWriteAdmin: false,
    } as unknown as ReturnType<typeof usePermissions>);

    render(<AccountsPanel />);

    expect(screen.queryByRole("button", { name: "Deposit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Withdraw" })).not.toBeInTheDocument();
  });

  it("renders the Deposit button with write:admin, opens the dialog, and bumps refresh + shows a banner on success", async () => {
    mockedUsePermissions.mockReturnValue({
      hasReadAdmin: true,
      hasWriteAdmin: true,
    } as unknown as ReturnType<typeof usePermissions>);

    render(<AccountsPanel />);

    const depositButton = screen.getByRole("button", { name: "Deposit" });
    expect(depositButton).toBeInTheDocument();
    expect(screen.getByTestId("accounts-list")).toHaveAttribute("data-refresh-token", "0");

    fireEvent.click(depositButton);
    expect(screen.getByTestId("deposit-dialog")).toBeInTheDocument();

    act(() => {
      capturedOnSuccess?.(
        { request_id: "r1", approved: true, amount_applied: 5000, new_balance: 15000 },
        ACCOUNT,
      );
    });

    await waitFor(() => expect(screen.getByTestId("accounts-list")).toHaveAttribute("data-refresh-token", "1"));
    expect(screen.getByText(/Deposited \$50.00 into 1111-1111-1111-1111/)).toBeInTheDocument();
    expect(screen.queryByTestId("deposit-dialog")).not.toBeInTheDocument();
  });

  it("renders the Withdraw button with write:admin, opens the dialog, and bumps refresh + shows a banner on success", async () => {
    mockedUsePermissions.mockReturnValue({
      hasReadAdmin: true,
      hasWriteAdmin: true,
    } as unknown as ReturnType<typeof usePermissions>);

    render(<AccountsPanel />);

    const withdrawButton = screen.getByRole("button", { name: "Withdraw" });
    expect(withdrawButton).toBeInTheDocument();
    expect(screen.getByTestId("accounts-list")).toHaveAttribute("data-refresh-token", "0");

    fireEvent.click(withdrawButton);
    expect(screen.getByTestId("withdrawal-dialog")).toBeInTheDocument();

    act(() => {
      capturedWithdrawOnSuccess?.(
        { request_id: "r1", approved: true, amount_applied: 5000, new_balance: 5000 },
        ACCOUNT,
      );
    });

    await waitFor(() => expect(screen.getByTestId("accounts-list")).toHaveAttribute("data-refresh-token", "1"));
    expect(screen.getByText(/Withdrew \$50.00 from 1111-1111-1111-1111/)).toBeInTheDocument();
    expect(screen.queryByTestId("withdrawal-dialog")).not.toBeInTheDocument();
  });
});
