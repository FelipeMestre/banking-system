import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { UpdateCardAccountStatusDialog } from "@/features/card-account-admin/components/UpdateCardAccountStatusDialog";
import * as updateStatusModule from "@/features/card-account-admin/api/update-card-account-status";

const CARD_ACCOUNT = {
  id: "ca-1",
  customer_id: "c-1",
  paying_account_id: "acc-1",
  credit_limit: "5000.00",
  status: "active" as const,
};

describe("UpdateCardAccountStatusDialog", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("closes the account and calls onSuccess on the happy path", async () => {
    const spy = vi
      .spyOn(updateStatusModule, "updateCardAccountStatus")
      .mockResolvedValue({ ...CARD_ACCOUNT, status: "closed" });
    const onSuccess = vi.fn();
    render(
      <UpdateCardAccountStatusDialog
        cardAccount={CARD_ACCOUNT}
        targetStatus="closed"
        onClose={vi.fn()}
        onSuccess={onSuccess}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Close card account" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    expect(spy).toHaveBeenCalledWith("ca-1", { status: "closed", reason: undefined });
  });

  it("surfaces the balance-guard 409 message verbatim on a failed close, not a generic failure", async () => {
    vi.spyOn(updateStatusModule, "updateCardAccountStatus").mockRejectedValue(
      new Error("card account ca-1 cannot be closed: outstanding balance 125.50"),
    );
    const onSuccess = vi.fn();
    render(
      <UpdateCardAccountStatusDialog
        cardAccount={CARD_ACCOUNT}
        targetStatus="closed"
        onClose={vi.fn()}
        onSuccess={onSuccess}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Close card account" }));

    expect(
      await screen.findByText("card account ca-1 cannot be closed: outstanding balance 125.50"),
    ).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
    expect(screen.queryByText(/could not update the account status/i)).not.toBeInTheDocument();
  });

  it("blocks the account without querying a balance guard", async () => {
    const spy = vi
      .spyOn(updateStatusModule, "updateCardAccountStatus")
      .mockResolvedValue({ ...CARD_ACCOUNT, status: "blocked" });
    render(
      <UpdateCardAccountStatusDialog
        cardAccount={CARD_ACCOUNT}
        targetStatus="blocked"
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Block card account" }));

    await waitFor(() => expect(spy).toHaveBeenCalledWith("ca-1", { status: "blocked", reason: undefined }));
  });
});
