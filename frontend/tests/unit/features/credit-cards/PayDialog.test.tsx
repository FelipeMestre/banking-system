import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PayDialog } from "@/features/credit-cards/components/PayDialog";
import * as requestPaymentModule from "@/features/credit-cards/api/request-payment";
import * as watchModule from "@/features/credit-cards/api/watch-payment-status";

describe("PayDialog", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("offers only a free-form amount field when no presets are supplied", () => {
    render(<PayDialog cardAccountId="ca-1" onClose={vi.fn()} />);

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

  it("blocks submit until a valid amount is entered", () => {
    render(<PayDialog cardAccountId="ca-1" onClose={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Submit payment" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });

    expect(screen.getByRole("button", { name: "Submit payment" })).not.toBeDisabled();
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
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));

    await waitFor(() =>
      expect(requestPaymentModule.requestPayment).toHaveBeenCalledWith("ca-1", { amount: 10000 }),
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
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));

    expect(await screen.findByText("pending")).toBeInTheDocument();
    act(() => deliverApproved?.());

    await waitFor(() => expect(onPaid).toHaveBeenCalledOnce());
  });
});
