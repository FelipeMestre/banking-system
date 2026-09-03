import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useTransferDraft } from "@/features/transfers/hooks/useTransferDraft";
import { findRecipient } from "@/features/transfers/api/find-recipient";
import type { Account } from "@/features/accounts";
import type { RecipientPreview } from "@/features/transfers/types";

vi.mock("@/features/transfers/api/find-recipient", () => ({ findRecipient: vi.fn() }));

const mockedFindRecipient = vi.mocked(findRecipient);

const RECIPIENTS: Record<string, RecipientPreview> = {
  "7723490011": { account_number: "7723490011", currency: "USD", name: "Alex Morgan", initials: "AM" },
  "8800001122": { account_number: "8800001122", currency: "EUR", name: "Sofia Rossi", initials: "SR" },
};

function mockRecipientLookup() {
  mockedFindRecipient.mockImplementation(async (accountNumber: string) => RECIPIENTS[accountNumber] ?? null);
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

describe("useTransferDraft selectors", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("derived: EUR from, USD hit, amount 10.00 → hasRecipient true warning true canConfirm true", async () => {
    mockRecipientLookup();
    const { result } = renderHook(() => useTransferDraft(mockAccounts));
    act(() => {
      result.current.setFromId("200000000002");
      result.current.setToNumber("7723490011");
      result.current.setAmount("10.00");
    });
    await waitFor(() => expect(result.current.hasRecipient).toBe(true));
    expect(result.current.recipient?.account_number).toBe("7723490011");
    expect(result.current.recipientNotFound).toBe(false);
    expect(result.current.showExchangeWarning).toBe(true);
    expect(result.current.canConfirm).toBe(true);
  });

  it("empty amount blocks canConfirm", async () => {
    mockRecipientLookup();
    const { result } = renderHook(() => useTransferDraft(mockAccounts));
    act(() => {
      result.current.setFromId("100000000001");
      result.current.setToNumber("8800001122");
      result.current.setAmount(" ");
    });
    await waitFor(() => expect(result.current.hasRecipient).toBe(true));
    expect(result.current.canConfirm).toBe(false);
  });

  it("recipientNotFound when >=6 digits not in directory", async () => {
    mockRecipientLookup();
    const { result } = renderHook(() => useTransferDraft(mockAccounts));
    act(() => {
      result.current.setToNumber("123456");
    });
    await waitFor(() => expect(result.current.recipientNotFound).toBe(true));
    expect(result.current.hasRecipient).toBe(false);
    expect(result.current.showExchangeWarning).toBe(false);
  });

  it("no warning when same currency", async () => {
    mockRecipientLookup();
    const { result } = renderHook(() => useTransferDraft(mockAccounts));
    act(() => {
      result.current.setFromId("100000000001");
      result.current.setToNumber("7723490011");
      result.current.setAmount("5");
    });
    await waitFor(() => expect(result.current.hasRecipient).toBe(true));
    expect(result.current.showExchangeWarning).toBe(false);
  });

  it("hasRecipient false when fewer than 6 digits", () => {
    mockRecipientLookup();
    const { result } = renderHook(() => useTransferDraft(mockAccounts));
    act(() => {
      result.current.setToNumber("123");
    });
    expect(result.current.hasRecipient).toBe(false);
    expect(result.current.recipientNotFound).toBe(false);
    expect(mockedFindRecipient).not.toHaveBeenCalled();
  });

  it("fromAccount derived from account_number and warning respects real accounts", async () => {
    mockRecipientLookup();
    const { result } = renderHook(() => useTransferDraft(mockAccounts));
    act(() => {
      result.current.setFromId("300000000003");
      result.current.setToNumber("8800001122");
      result.current.setAmount("1.00");
    });
    expect(result.current.fromAccount?.account_number).toBe("300000000003");
    expect(result.current.fromAccount?.currency).toBe("GBP");
    // GBP -> EUR should warn
    await waitFor(() => expect(result.current.showExchangeWarning).toBe(true));
  });

  it("empty accounts: fromAccount null but hook still functional", async () => {
    mockRecipientLookup();
    const { result } = renderHook(() => useTransferDraft([]));
    act(() => {
      result.current.setToNumber("7723490011");
      result.current.setAmount("10.00");
    });
    expect(result.current.fromAccount).toBeNull();
    await waitFor(() => expect(result.current.hasRecipient).toBe(true));
    expect(result.current.showExchangeWarning).toBe(false);
  });

  it("surfaces a lookup failure distinctly from not-found", async () => {
    mockedFindRecipient.mockRejectedValue(new Error("gateway unreachable"));
    const { result } = renderHook(() => useTransferDraft(mockAccounts));
    act(() => {
      result.current.setToNumber("555555");
    });
    await waitFor(() => expect(result.current.recipientError).toBe("gateway unreachable"));
    expect(result.current.hasRecipient).toBe(false);
    expect(result.current.recipientNotFound).toBe(false);
  });
});
