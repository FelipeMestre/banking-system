import { render, screen, fireEvent } from "@testing-library/react";
import { describe, afterEach, beforeAll, expect, it, vi } from "vitest";
import { TransferPanel } from "@/features/transfers/components/TransferPanel";
import { FromAccountSelect } from "@/features/transfers/components/FromAccountSelect";
import { findRecipient } from "@/features/transfers/api/find-recipient";
import type { Account } from "@/features/accounts";

vi.mock("@/features/transfers/api/find-recipient", () => ({ findRecipient: vi.fn() }));

const mockedFindRecipient = vi.mocked(findRecipient);

beforeAll(() => {
  // jsdom lacks scrollIntoView; Radix Select calls it on open
  Element.prototype.scrollIntoView = vi.fn() as unknown as typeof Element.prototype.scrollIntoView;
  HTMLElement.prototype.scrollIntoView = vi.fn() as unknown as typeof HTMLElement.prototype.scrollIntoView;
});

const mockAccounts: Account[] = [
  {
    id: "1",
    account_number: "100000000001",
    currency: "USD",
    customer_id: "c1",
    branch_id: "b1",
    balance: 125000,
    status: "active",
  },
  {
    id: "2",
    account_number: "200000000002",
    currency: "EUR",
    customer_id: "c1",
    branch_id: "b1",
    balance: 89000,
    status: "active",
  },
  {
    id: "3",
    account_number: "300000000003",
    currency: "GBP",
    customer_id: "c1",
    branch_id: "b1",
    balance: 45000,
    status: "active",
  },
];

describe("TransferPanel integration", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("preview hit shows initials name and masked account when the account is found", async () => {
    mockedFindRecipient.mockResolvedValue({
      account_number: "7723490011", currency: "USD", name: "Alex Morgan", initials: "AM",
    });
    render(<TransferPanel accounts={mockAccounts} />);
    const input = screen.getByPlaceholderText("Enter the recipient's account number");
    fireEvent.change(input, { target: { value: "7723490011" } });
    // after >=6 digits, preview should appear
    expect(await screen.findByText("Alex Morgan")).toBeInTheDocument();
    expect(screen.getByText("AM")).toBeInTheDocument();
    expect(screen.getByText("•••• 0011 · USD")).toBeInTheDocument();
    expect(mockedFindRecipient).toHaveBeenCalledWith("7723490011");
  });

  it("preview miss shows No account found when the account doesn't exist", async () => {
    mockedFindRecipient.mockResolvedValue(null);
    render(<TransferPanel accounts={mockAccounts} />);
    const input = screen.getByPlaceholderText("Enter the recipient's account number");
    fireEvent.change(input, { target: { value: "999999" } });
    expect(await screen.findByText("No account found")).toBeInTheDocument();
    expect(screen.getByTestId("recipient-preview-live")).toBeInTheDocument();
  });

  it("a lookup failure shows the error message, not No account found", async () => {
    mockedFindRecipient.mockRejectedValue(new Error("gateway unreachable"));
    render(<TransferPanel accounts={mockAccounts} />);
    const input = screen.getByPlaceholderText("Enter the recipient's account number");
    fireEvent.change(input, { target: { value: "999999" } });
    expect(await screen.findByText("gateway unreachable")).toBeInTheDocument();
    expect(screen.queryByText("No account found")).not.toBeInTheDocument();
  });

  it("shows exchange warning only when cross-currency", async () => {
    mockedFindRecipient.mockResolvedValue({
      account_number: "7723490011", currency: "USD", name: "Alex Morgan", initials: "AM",
    });
    render(<TransferPanel initialFromId="200000000002" accounts={mockAccounts} />);
    // 200000000002 is EUR, recipient 7723490011 is USD → warning
    const input = screen.getByPlaceholderText("Enter the recipient's account number");
    fireEvent.change(input, { target: { value: "7723490011" } });
    expect(await screen.findByText(/This transfer moves EUR into USD/)).toBeInTheDocument();
    expect(screen.getByText("Exchange rate locked at confirmation")).toBeInTheDocument();
  });

  it("does not show warning when same currency", async () => {
    mockedFindRecipient.mockResolvedValue({
      account_number: "7723490011", currency: "USD", name: "Alex Morgan", initials: "AM",
    });
    render(<TransferPanel initialFromId="100000000001" accounts={mockAccounts} />);
    const input = screen.getByPlaceholderText("Enter the recipient's account number");
    fireEvent.change(input, { target: { value: "7723490011" } });
    expect(await screen.findByText("Alex Morgan")).toBeInTheDocument();
    expect(screen.queryByText(/This transfer moves/)).not.toBeInTheDocument();
  });

  it("Confirm button disabled unless canConfirm and enabled after amount entered", async () => {
    mockedFindRecipient.mockResolvedValue({
      account_number: "7723490011", currency: "USD", name: "Alex Morgan", initials: "AM",
    });
    render(<TransferPanel accounts={mockAccounts} />);
    const confirm = screen.getByRole("button", { name: /Confirm transfer/i });
    expect(confirm).toBeDisabled();
    const toInput = screen.getByPlaceholderText("Enter the recipient's account number");
    fireEvent.change(toInput, { target: { value: "7723490011" } });
    await screen.findByText("Alex Morgan");
    // still disabled without amount
    expect(confirm).toBeDisabled();
    const amount = screen.getByPlaceholderText("0.00");
    fireEvent.change(amount, { target: { value: "10.00" } });
    expect(confirm).not.toBeDisabled();
  });

  it("FromAccountSelect renders options from accounts prop", async () => {
    render(<FromAccountSelect value="100000000001" onChange={() => {}} accounts={mockAccounts} />);
    const trigger = screen.getByLabelText("From account");
    // trigger shows selected value derived from accounts prop
    expect(trigger).toHaveTextContent("USD account");
    expect(trigger).toHaveTextContent("•••• 0001");
    fireEvent.click(trigger);
    expect(await screen.findByRole("option", { name: /USD account/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /EUR account/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /GBP account/ })).toBeInTheDocument();
  });

  it("FromAccountSelect is disabled and shows placeholder when no accounts", async () => {
    render(<FromAccountSelect value="" onChange={() => {}} accounts={[]} />);
    const trigger = screen.getByLabelText("From account");
    expect(trigger).toBeDisabled();
  });

  it("Confirm button stays disabled when no accounts available", async () => {
    mockedFindRecipient.mockResolvedValue({
      account_number: "7723490011", currency: "USD", name: "Alex Morgan", initials: "AM",
    });
    render(<TransferPanel accounts={[]} />);
    const confirm = screen.getByRole("button", { name: /Confirm transfer/i });
    expect(confirm).toBeDisabled();
    // even with recipient and amount, still disabled because no accounts
    fireEvent.change(screen.getByPlaceholderText("Enter the recipient's account number"), {
      target: { value: "7723490011" },
    });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "10.00" } });
    await screen.findByText("Alex Morgan");
    expect(confirm).toBeDisabled();
  });
});
