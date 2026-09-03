import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TransferPageScreen } from "@/features/transfers/components/TransferPageScreen";

describe("TransferPageScreen workspace", () => {
  it("renders header Send a transfer with OpenBank and 10px strip", () => {
    render(<TransferPageScreen />);
    expect(screen.getByText("Send a transfer")).toBeInTheDocument();
    expect(screen.getByText("OpenBank")).toBeInTheDocument();
  });

  it("overlay appears on submit and shows aria-busy", async () => {
    render(<TransferPageScreen />);
    const toInput = screen.getByPlaceholderText("Enter the recipient's account number");
    const amount = screen.getByPlaceholderText("0.00");
    fireEvent.change(toInput, { target: { value: "8800001122" } });
    fireEvent.change(amount, { target: { value: "10.00" } });
    const confirm = screen.getByRole("button", { name: /Confirm transfer/i });
    expect(confirm).not.toBeDisabled();
    fireEvent.click(confirm);
    expect(screen.getByTestId("processing-overlay")).toBeInTheDocument();
    expect(screen.getByText("Processing your transfer")).toBeInTheDocument();
    expect(screen.getByTestId("processing-overlay")).toHaveAttribute("aria-busy", "true");
  });

  it("7723490011 fails after 1400ms with error modal", async () => {
    render(<TransferPageScreen />);
    fireEvent.change(screen.getByPlaceholderText("Enter the recipient's account number"), {
      target: { value: "7723490011" },
    });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "5.00" } });
    fireEvent.click(screen.getByRole("button", { name: /Confirm transfer/i }));
    expect(screen.getByTestId("processing-overlay")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Error in the operation")).toBeInTheDocument(), {
      timeout: 3000,
    });
    expect(screen.getByText("Try again")).toBeInTheDocument();
    expect(screen.queryByTestId("processing-overlay")).not.toBeInTheDocument();
  }, 5000);

  it("other number succeeds after 1400ms with success modal", async () => {
    render(<TransferPageScreen />);
    fireEvent.change(screen.getByPlaceholderText("Enter the recipient's account number"), {
      target: { value: "8800001122" },
    });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "5.00" } });
    fireEvent.click(screen.getByRole("button", { name: /Confirm transfer/i }));
    await waitFor(() => expect(screen.getByText("Success in the operation")).toBeInTheDocument(), {
      timeout: 3000,
    });
    expect(screen.getByText("Go to Homepage")).toBeInTheDocument();
    const link = screen.getByText("Go to Homepage").closest("a");
    expect(link).toHaveAttribute("href", "/");
  }, 5000);

  it("Try again dismisses modal", async () => {
    render(<TransferPageScreen />);
    fireEvent.change(screen.getByPlaceholderText("Enter the recipient's account number"), {
      target: { value: "7723490011" },
    });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "5.00" } });
    fireEvent.click(screen.getByRole("button", { name: /Confirm transfer/i }));
    await waitFor(() => expect(screen.getByText("Error in the operation")).toBeInTheDocument(), {
      timeout: 3000,
    });
    fireEvent.click(screen.getByText("Try again"));
    expect(screen.queryByText("Error in the operation")).not.toBeInTheDocument();
  }, 5000);

  it("a11y labels and live regions present", () => {
    render(<TransferPageScreen />);
    expect(screen.getByLabelText("From account")).toBeInTheDocument();
    expect(screen.getByLabelText("To account")).toBeInTheDocument();
    expect(screen.getByLabelText("Amount")).toBeInTheDocument();
    // aria-live in ToAccountField appears after typing >=6
    fireEvent.change(screen.getByPlaceholderText("Enter the recipient's account number"), {
      target: { value: "123456" },
    });
    expect(screen.getByTestId("recipient-preview-live")).toHaveAttribute("aria-live", "polite");
  });
});
