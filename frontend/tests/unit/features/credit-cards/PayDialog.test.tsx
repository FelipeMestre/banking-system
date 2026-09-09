import { useState } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PayDialog } from "@/features/credit-cards/components/PayDialog";
import * as accountsModule from "@/features/accounts/api/get-accounts";
import * as requestPaymentModule from "@/features/credit-cards/api/request-payment";
import * as watchModule from "@/features/credit-cards/api/watch-payment-status";
import type { Account } from "@/features/accounts";

const OWN_ACCOUNT: Account = {
  id: "a1", account_number: "1111222233334444", currency: "USD",
  customer_id: "c1", branch_id: "b1", balance: 500000, status: "active",
};

/** Stands in for `CreditCardsPageScreen`: a parent that reacts to `onPaid`
 * by updating its own state, the same shape `refreshCardsAfterPayment`
 * takes there. Reproduces the exact "setState of a different component
 * during render" hazard PayDialog's `applyStatus` used to trigger. */
function HostingParent() {
  const [refreshCount, setRefreshCount] = useState(0);
  return (
    <div>
      <p>Refreshed {refreshCount} times</p>
      <PayDialog cardAccountId="ca-1" onClose={vi.fn()} onPaid={() => setRefreshCount((n) => n + 1)} />
    </div>
  );
}

describe("PayDialog", () => {
  // jsdom doesn't implement these, which Radix's Select relies on when
  // opening its option list.
  Element.prototype.hasPointerCapture = vi.fn().mockReturnValue(false);
  Element.prototype.scrollIntoView = vi.fn();

  beforeEach(() => {
    vi.spyOn(accountsModule, "getAccounts").mockResolvedValue({
      items: [OWN_ACCOUNT], total: 1, limit: 50, offset: 0,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("offers a source account picker and a free-form amount field when no presets are supplied", async () => {
    render(<PayDialog cardAccountId="ca-1" onClose={vi.fn()} />);

    expect(await screen.findByLabelText("Pay from")).toBeInTheDocument();
    expect(screen.getByLabelText("Amount")).toBeInTheDocument();
    expect(screen.queryByText(/pay minimum/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/pay in full/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/settle installments early/i)).not.toBeInTheDocument();
  });

  it("shows quick-select presets and fills the amount field when clicked (credit-card-monthly-batch-statements)", () => {
    render(
      <PayDialog
        cardAccountId="ca-1"
        onClose={vi.fn()}
        presets={{ minimum: "15.00", full: "120.00", installmentPayoff: "300.00" }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Pay minimum/ }));
    expect(screen.getByLabelText("Amount")).toHaveValue("15.00");

    fireEvent.click(screen.getByRole("button", { name: /Settle installments early/ }));
    expect(screen.getByLabelText("Amount")).toHaveValue("300.00");

    fireEvent.click(screen.getByRole("button", { name: /Pay in full/ }));
    expect(screen.getByLabelText("Amount")).toHaveValue("120.00");
  });

  it("hides the settle-installments preset when the payoff amount is zero", () => {
    render(
      <PayDialog
        cardAccountId="ca-1"
        onClose={vi.fn()}
        presets={{ minimum: "15.00", full: "120.00", installmentPayoff: "0.00" }}
      />,
    );

    expect(screen.queryByText(/settle installments early/i)).not.toBeInTheDocument();
  });

  it("blocks submit until a valid amount is entered", async () => {
    render(<PayDialog cardAccountId="ca-1" onClose={vi.fn()} />);
    await screen.findByLabelText("Pay from");

    expect(screen.getByRole("button", { name: "Submit payment" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });

    expect(screen.getByRole("button", { name: "Submit payment" })).not.toBeDisabled();
  });

  it("lets the customer pick which of their own accounts pays the card", async () => {
    const secondAccount: Account = {
      id: "a2", account_number: "5555666677778888", currency: "EUR",
      customer_id: "c1", branch_id: "b1", balance: 200000, status: "active",
    };
    vi.spyOn(accountsModule, "getAccounts").mockResolvedValue({
      items: [OWN_ACCOUNT, secondAccount], total: 2, limit: 50, offset: 0,
    });
    vi.spyOn(requestPaymentModule, "requestPayment").mockResolvedValue({
      request_id: "r1", status: "pending",
    });
    vi.spyOn(watchModule, "watchPaymentStatus").mockImplementation(() => () => {});

    render(<PayDialog cardAccountId="ca-1" onClose={vi.fn()} />);
    const picker = await screen.findByLabelText("Pay from");

    // Defaults to the first account until the customer picks another.
    expect(picker).toHaveTextContent(OWN_ACCOUNT.account_number.slice(-4));

    fireEvent.click(picker);
    fireEvent.click(await screen.findByRole("option", { name: /EUR account/ }));
    expect(picker).toHaveTextContent(secondAccount.account_number.slice(-4));

    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "50.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));

    await waitFor(() =>
      expect(requestPaymentModule.requestPayment).toHaveBeenCalledWith("ca-1", {
        amount: 5000, source_account: secondAccount.account_number,
      }),
    );
  });

  it("blocks submit when the customer has no accounts to pay from", async () => {
    vi.spyOn(accountsModule, "getAccounts").mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    render(<PayDialog cardAccountId="ca-1" onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByLabelText("Pay from")).toBeDisabled());

    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });

    expect(screen.getByRole("button", { name: "Submit payment" })).toBeDisabled();
  });

  it("submits the amount as integer cents and transitions pending -> approved via the live watcher", async () => {
    vi.spyOn(requestPaymentModule, "requestPayment").mockResolvedValue({
      request_id: "r1", status: "pending",
    });
    let deliverApproved: (() => void) | undefined;
    vi.spyOn(watchModule, "watchPaymentStatus").mockImplementation((_requestId, watcher) => {
      deliverApproved = () => watcher.onStatus({ request_id: "r1", status: "approved" });
      return () => {};
    });

    render(<PayDialog cardAccountId="ca-1" onClose={vi.fn()} />);
    await screen.findByLabelText("Pay from");
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));

    await waitFor(() =>
      expect(requestPaymentModule.requestPayment).toHaveBeenCalledWith("ca-1", {
        amount: 10000, source_account: OWN_ACCOUNT.account_number,
      }),
    );
    expect(await screen.findByText("pending")).toBeInTheDocument();

    act(() => deliverApproved?.());

    expect(await screen.findByText("approved")).toBeInTheDocument();
  });

  it("calls onPaid once the live status resolves to approved", async () => {
    vi.spyOn(requestPaymentModule, "requestPayment").mockResolvedValue({
      request_id: "r1", status: "pending",
    });
    let deliverApproved: (() => void) | undefined;
    vi.spyOn(watchModule, "watchPaymentStatus").mockImplementation((_requestId, watcher) => {
      deliverApproved = () => watcher.onStatus({ request_id: "r1", status: "approved" });
      return () => {};
    });
    const onPaid = vi.fn();

    render(<PayDialog cardAccountId="ca-1" onClose={vi.fn()} onPaid={onPaid} />);
    await screen.findByLabelText("Pay from");
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));

    expect(await screen.findByText("pending")).toBeInTheDocument();
    act(() => deliverApproved?.());

    await waitFor(() => expect(onPaid).toHaveBeenCalledOnce());
  });

  it("shows a single Close button once the payment resolves, not a Cancel and a Close saying the same thing", async () => {
    vi.spyOn(requestPaymentModule, "requestPayment").mockResolvedValue({
      request_id: "r1", status: "pending",
    });
    vi.spyOn(watchModule, "watchPaymentStatus").mockImplementation(() => () => {});

    render(<PayDialog cardAccountId="ca-1" onClose={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    await screen.findByLabelText("Pay from");

    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));

    // The dialog's own "X" icon button is separately aria-labeled "Close" —
    // scope to the visible text so this only counts the footer buttons.
    expect(await screen.findByText("Close")).toBeInTheDocument();
    expect(screen.getAllByText("Close")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });

  it("never updates the parent (onPaid) from inside a setState updater — the exact 'Cannot update a component while rendering a different component' hazard", async () => {
    vi.spyOn(requestPaymentModule, "requestPayment").mockResolvedValue({
      request_id: "r1", status: "pending",
    });
    let deliverApproved: (() => void) | undefined;
    vi.spyOn(watchModule, "watchPaymentStatus").mockImplementation((_requestId, watcher) => {
      deliverApproved = () => watcher.onStatus({ request_id: "r1", status: "approved" });
      return () => {};
    });
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    render(<HostingParent />);
    await screen.findByLabelText("Pay from");
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));
    await screen.findByText("pending");

    act(() => deliverApproved?.());

    await waitFor(() => expect(screen.getByText("Refreshed 1 times")).toBeInTheDocument());
    const renderPhaseViolation = consoleError.mock.calls.some((call) =>
      String(call[0]).includes("Cannot update a component") && String(call[0]).includes("while rendering"),
    );
    expect(renderPhaseViolation).toBe(false);
  });
});
