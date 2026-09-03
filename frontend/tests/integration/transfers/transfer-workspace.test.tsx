import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TransferPageScreen } from "@/features/transfers/components/TransferPageScreen";
import { requestTransfer } from "@/features/transfers/api/request-transfer";
import { watchTransferStatus } from "@/features/transfers/api/watch-transfer-status";
import { findRecipient } from "@/features/transfers/api/find-recipient";
import type { Account } from "@/features/accounts";
import type { TransferStatus } from "@/features/transfers/types";

vi.mock("@/features/transfers/api/request-transfer", () => ({ requestTransfer: vi.fn() }));
vi.mock("@/features/transfers/api/watch-transfer-status", () => ({ watchTransferStatus: vi.fn() }));
vi.mock("@/features/transfers/api/find-recipient", () => ({ findRecipient: vi.fn() }));

const mockedRequestTransfer = vi.mocked(requestTransfer);
const mockedWatchTransferStatus = vi.mocked(watchTransferStatus);
const mockedFindRecipient = vi.mocked(findRecipient);

const RECIPIENTS: Record<string, { account_number: string; currency: string; name: string; initials: string }> = {
  "7723490011": { account_number: "7723490011", currency: "USD", name: "Alex Morgan", initials: "AM" },
  "8800001122": { account_number: "8800001122", currency: "EUR", name: "Sofia Rossi", initials: "SR" },
};

beforeEach(() => {
  mockedFindRecipient.mockImplementation(async (accountNumber: string) => RECIPIENTS[accountNumber] ?? null);
});

/** Simulates the gateway delivering `status` over the WebSocket right after accept. */
function watchResolvesWith(status: TransferStatus) {
  mockedWatchTransferStatus.mockImplementation((_requestId, watcher) => {
    queueMicrotask(() => watcher.onStatus(status));
    return () => {};
  });
}

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

const ACCOUNTS_PAGE = {
  items: mockAccounts,
  total: mockAccounts.length,
  limit: 50,
  offset: 0,
};

function mockAccountsFetch() {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(ACCOUNTS_PAGE), { status: 200 }),
  );
}

describe("TransferPageScreen workspace", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders header Send a transfer with OpenBank and 10px strip", async () => {
    mockAccountsFetch();
    render(<TransferPageScreen />);
    expect(screen.getByText("Send a transfer")).toBeInTheDocument();
    expect(screen.getByText("OpenBank")).toBeInTheDocument();
    // wait for accounts to load so panel renders
    await waitFor(() => expect(screen.getByLabelText("From account")).toBeInTheDocument());
  });

  it("overlay appears on submit and shows aria-busy", async () => {
    mockAccountsFetch();
    mockedRequestTransfer.mockReturnValue(new Promise(() => {})); // never resolves during this test
    render(<TransferPageScreen />);
    await waitFor(() => expect(screen.getByLabelText("From account")).toBeInTheDocument());
    const toInput = screen.getByPlaceholderText("Enter the recipient's account number");
    const amount = screen.getByPlaceholderText("0.00");
    fireEvent.change(toInput, { target: { value: "8800001122" } });
    fireEvent.change(amount, { target: { value: "10.00" } });
    await screen.findByText("Sofia Rossi");
    const confirm = screen.getByRole("button", { name: /Confirm transfer/i });
    expect(confirm).not.toBeDisabled();
    fireEvent.click(confirm);
    expect(screen.getByTestId("processing-overlay")).toBeInTheDocument();
    expect(screen.getByText("Processing your transfer")).toBeInTheDocument();
    expect(screen.getByTestId("processing-overlay")).toHaveAttribute("aria-busy", "true");
  });

  it("a declined verdict from the ledger shows the error modal", async () => {
    mockAccountsFetch();
    mockedRequestTransfer.mockResolvedValue({ request_id: "req-1", status: "pending", fee_amount: 25 });
    watchResolvesWith({ request_id: "req-1", status: "declined", reason: "Transfer failed: insufficient funds" });
    render(<TransferPageScreen />);
    await waitFor(() => expect(screen.getByLabelText("From account")).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText("Enter the recipient's account number"), {
      target: { value: "7723490011" },
    });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "5.00" } });
    await screen.findByText("Alex Morgan");
    fireEvent.click(screen.getByRole("button", { name: /Confirm transfer/i }));
    expect(screen.getByTestId("processing-overlay")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Error in the operation")).toBeInTheDocument());
    expect(screen.getByText("Try again")).toBeInTheDocument();
    expect(screen.queryByTestId("processing-overlay")).not.toBeInTheDocument();
    expect(mockedRequestTransfer).toHaveBeenCalledWith({
      source_account: "100000000001",
      destination_account: "7723490011",
      amount: 500,
    });
  });

  it("an approved verdict from the ledger shows the success modal", async () => {
    mockAccountsFetch();
    mockedRequestTransfer.mockResolvedValue({ request_id: "req-2", status: "pending", fee_amount: 25 });
    watchResolvesWith({ request_id: "req-2", status: "approved" });
    render(<TransferPageScreen />);
    await waitFor(() => expect(screen.getByLabelText("From account")).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText("Enter the recipient's account number"), {
      target: { value: "8800001122" },
    });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "5.00" } });
    await screen.findByText("Sofia Rossi");
    fireEvent.click(screen.getByRole("button", { name: /Confirm transfer/i }));
    await waitFor(() => expect(screen.getByText("Success in the operation")).toBeInTheDocument());
    expect(screen.getByText("Go to Homepage")).toBeInTheDocument();
    const link = screen.getByText("Go to Homepage").closest("a");
    expect(link).toHaveAttribute("href", "/");
  });

  it("Try again dismisses the error modal", async () => {
    mockAccountsFetch();
    mockedRequestTransfer.mockResolvedValue({ request_id: "req-3", status: "pending", fee_amount: 25 });
    watchResolvesWith({ request_id: "req-3", status: "declined", reason: "Transfer failed: insufficient funds" });
    render(<TransferPageScreen />);
    await waitFor(() => expect(screen.getByLabelText("From account")).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText("Enter the recipient's account number"), {
      target: { value: "7723490011" },
    });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "5.00" } });
    await screen.findByText("Alex Morgan");
    fireEvent.click(screen.getByRole("button", { name: /Confirm transfer/i }));
    await waitFor(() => expect(screen.getByText("Error in the operation")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Try again"));
    expect(screen.queryByText("Error in the operation")).not.toBeInTheDocument();
  });

  it("falls back to a poll when the socket closes without a verdict", async () => {
    mockAccountsFetch();
    mockedRequestTransfer.mockResolvedValue({ request_id: "req-4", status: "pending", fee_amount: 25 });
    mockedWatchTransferStatus.mockImplementation((_requestId, watcher) => {
      queueMicrotask(() => watcher.onUnavailable());
      return () => {};
    });
    const getTransferStatusSpy = vi
      .spyOn(await import("@/features/transfers/api/get-transfer-status"), "getTransferStatus")
      .mockResolvedValue({ request_id: "req-4", status: "approved" });

    render(<TransferPageScreen />);
    await waitFor(() => expect(screen.getByLabelText("From account")).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText("Enter the recipient's account number"), {
      target: { value: "8800001122" },
    });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "5.00" } });
    await screen.findByText("Sofia Rossi");
    fireEvent.click(screen.getByRole("button", { name: /Confirm transfer/i }));

    await waitFor(() => expect(screen.getByText("Success in the operation")).toBeInTheDocument());
    expect(getTransferStatusSpy).toHaveBeenCalledWith("req-4");
  });

  it("a11y labels and live regions present", async () => {
    mockAccountsFetch();
    render(<TransferPageScreen />);
    await waitFor(() => expect(screen.getByLabelText("From account")).toBeInTheDocument());
    expect(screen.getByLabelText("To account number")).toBeInTheDocument();
    expect(screen.getByLabelText("Amount")).toBeInTheDocument();
    // aria-live in ToAccountField appears after typing >=6
    fireEvent.change(screen.getByPlaceholderText("Enter the recipient's account number"), {
      target: { value: "123456" },
    });
    expect(screen.getByTestId("recipient-preview-live")).toHaveAttribute("aria-live", "polite");
    await screen.findByText("No account found");
  });

  it("shows loading state initially and then renders panel", async () => {
    let resolveFetch: (value: Response) => void;
    const pendingPromise = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
    vi.spyOn(globalThis, "fetch").mockReturnValue(pendingPromise as unknown as Promise<Response>);

    render(<TransferPageScreen />);

    expect(screen.getByRole("status", { name: "Loading your accounts" })).toBeInTheDocument();

    resolveFetch!(new Response(JSON.stringify(ACCOUNTS_PAGE), { status: 200 }));

    await waitFor(() => expect(screen.getByLabelText("From account")).toBeInTheDocument());
  });

  it("shows error message when accounts fetch fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "internal server error" } }), { status: 500 }),
    );

    render(<TransferPageScreen />);

    expect(await screen.findByText("internal server error")).toBeInTheDocument();
    expect(screen.queryByLabelText("From account")).not.toBeInTheDocument();
  });

  it("treats 404 as empty and shows No accounts to show", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "no linked customer" } }), { status: 404 }),
    );

    render(<TransferPageScreen />);

    expect(await screen.findByText("No accounts to show")).toBeInTheDocument();
  });
});
