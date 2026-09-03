import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TransferPanel } from "@/features/transfers/components/TransferPanel";

const mockFromId = "acc-1";

describe("TransferPanel integration", () => {
  it("preview hit shows initials name and masked account when >=6 digits in directory", async () => {
    render(<TransferPanel />);
    const input = screen.getByPlaceholderText("Enter the recipient's account number");
    fireEvent.change(input, { target: { value: "7723490011" } });
    // after >=6 digits, preview should appear
    expect(await screen.findByText("Alex Morgan")).toBeInTheDocument();
    expect(screen.getByText("AM")).toBeInTheDocument();
    expect(screen.getByText("•••• 0011 · USD")).toBeInTheDocument();
  });

  it("preview miss shows No account found when >=6 digits not in directory", async () => {
    render(<TransferPanel />);
    const input = screen.getByPlaceholderText("Enter the recipient's account number");
    fireEvent.change(input, { target: { value: "999999" } });
    expect(await screen.findByText("No account found")).toBeInTheDocument();
    expect(screen.getByTestId("recipient-preview-live")).toBeInTheDocument();
  });

  it("shows exchange warning only when cross-currency", async () => {
    render(<TransferPanel initialFromId="acc-2" />);
    // acc-2 is EUR, recipient 7723490011 is USD → warning
    const input = screen.getByPlaceholderText("Enter the recipient's account number");
    fireEvent.change(input, { target: { value: "7723490011" } });
    expect(await screen.findByText(/This transfer moves EUR into USD/)).toBeInTheDocument();
    expect(screen.getByText("Exchange rate locked at confirmation")).toBeInTheDocument();
  });

  it("does not show warning when same currency", async () => {
    render(<TransferPanel initialFromId="acc-1" />);
    const input = screen.getByPlaceholderText("Enter the recipient's account number");
    fireEvent.change(input, { target: { value: "7723490011" } });
    expect(await screen.findByText("Alex Morgan")).toBeInTheDocument();
    expect(screen.queryByText(/This transfer moves/)).not.toBeInTheDocument();
  });

  it("Confirm button disabled unless canConfirm and enabled after amount entered", async () => {
    render(<TransferPanel />);
    const confirm = screen.getByRole("button", { name: /Confirm transfer/i });
    expect(confirm).toBeDisabled();
    const toInput = screen.getByPlaceholderText("Enter the recipient's account number");
    fireEvent.change(toInput, { target: { value: "7723490011" } });
    // still disabled without amount
    expect(confirm).toBeDisabled();
    const amount = screen.getByPlaceholderText("0.00");
    fireEvent.change(amount, { target: { value: "10.00" } });
    expect(confirm).not.toBeDisabled();
  });
});
