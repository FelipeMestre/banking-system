import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CreateAccountDialog } from "@/features/accounts/components/CreateAccountDialog";
import * as createAccountModule from "@/features/accounts/api/create-account";

describe("CreateAccountDialog", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the Terms and Conditions copy", () => {
    render(<CreateAccountDialog onClose={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.getByText(/USD/i)).toBeInTheDocument();
    expect(screen.getByText(/deposit agreement/i)).toBeInTheDocument();
    expect(screen.getByText(/identity/i)).toBeInTheDocument();
    expect(screen.getByText(/zero balance/i)).toBeInTheDocument();
  });

  it("closes with no request when Decline is selected", () => {
    const onClose = vi.fn();
    const createAccountSpy = vi.spyOn(createAccountModule, "createAccount");
    render(<CreateAccountDialog onClose={onClose} onSuccess={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Decline" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(createAccountSpy).not.toHaveBeenCalled();
  });

  it("calls createAccount and onSuccess when Accept is selected", async () => {
    vi.spyOn(createAccountModule, "createAccount").mockResolvedValue({
      id: "a1", account_number: "1111111111111111", currency: "USD",
      customer_id: "c1", branch_id: "b1", balance: 0, status: "active",
    });
    const onSuccess = vi.fn();
    render(<CreateAccountDialog onClose={vi.fn()} onSuccess={onSuccess} />);

    fireEvent.click(screen.getByRole("button", { name: "Accept and open account" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
  });

  it("shows an inline error and does not crash when creation fails with a 409", async () => {
    vi.spyOn(createAccountModule, "createAccount").mockRejectedValue(
      new Error("customer already owns an account"),
    );
    render(<CreateAccountDialog onClose={vi.fn()} onSuccess={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Accept and open account" }));

    expect(await screen.findByText("customer already owns an account")).toBeInTheDocument();
  });

  it("renders no KYC fields when requiresKyc is false (regression)", () => {
    render(<CreateAccountDialog onClose={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.queryByLabelText(/identification number/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/first name/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/date of birth/i)).not.toBeInTheDocument();
  });

  it("renders KYC fields, blocks Accept until required fields are filled, and includes them in createAccount when requiresKyc is true", async () => {
    const createAccountSpy = vi.spyOn(createAccountModule, "createAccount").mockResolvedValue({
      id: "a1", account_number: "1111111111111111", currency: "USD",
      customer_id: "c1", branch_id: "b1", balance: 0, status: "active",
    });
    const onSuccess = vi.fn();
    render(<CreateAccountDialog onClose={vi.fn()} onSuccess={onSuccess} requiresKyc />);

    expect(screen.getByLabelText(/identification number/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Accept and open account" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/identification number/i), { target: { value: "ID-1" } });
    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: "Jane" } });
    fireEvent.change(screen.getByLabelText(/last name/i), { target: { value: "Doe" } });
    fireEvent.change(screen.getByLabelText(/date of birth/i), { target: { value: "1990-01-15" } });

    const acceptButton = screen.getByRole("button", { name: "Accept and open account" });
    expect(acceptButton).not.toBeDisabled();
    fireEvent.click(acceptButton);

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    expect(createAccountSpy).toHaveBeenCalledWith({
      identification_number: "ID-1",
      first_name: "Jane",
      last_name: "Doe",
      date_of_birth: "1990-01-15",
    });
  });
});
