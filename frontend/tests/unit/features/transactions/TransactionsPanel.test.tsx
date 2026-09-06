import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TransactionsPanel } from "@/features/transactions/components/TransactionsPanel";
import { getTransactions } from "@/features/transactions/api/get-transactions";
import type { Transaction } from "@/features/transactions/types";

vi.mock("@/features/transactions/api/get-transactions", () => ({ getTransactions: vi.fn() }));

const mockedGetTransactions = vi.mocked(getTransactions);

class FakeIntersectionObserver {
  static instances: FakeIntersectionObserver[] = [];
  callback: IntersectionObserverCallback;
  observed: Element[] = [];

  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
    FakeIntersectionObserver.instances.push(this);
  }

  observe(el: Element) {
    this.observed.push(el);
  }

  disconnect() {}
  unobserve() {}

  trigger(isIntersecting: boolean) {
    this.callback(
      [{ isIntersecting } as IntersectionObserverEntry],
      this as unknown as IntersectionObserver,
    );
  }
}

function transaction(id: string): Transaction {
  return {
    id, request_id: `r-${id}`, type: "credit", amount: 1000,
    counterparty_account: "9999999999999999", decline_reason: null, ts: "2026-09-04T00:00:00Z",
  };
}

describe("TransactionsPanel", () => {
  beforeEach(() => {
    FakeIntersectionObserver.instances = [];
    vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders the first page inside a fixed-height, responsive scroll container", async () => {
    mockedGetTransactions.mockResolvedValue({ items: [transaction("t1")], next_cursor: null });

    render(<TransactionsPanel accountNumber="1111111111111111" currencyCode="USD" />);

    await waitFor(() => expect(screen.getByTestId("transactions-scroll-container")).toBeInTheDocument());
    const container = screen.getByTestId("transactions-scroll-container");
    expect(container.className).toContain("overflow-y-auto");
    expect(container.className).toContain("max-h-[140px]");
    expect(container.className).toContain("sm:max-h-[165px]");
    expect(container.className).toContain("lg:max-h-[190px]");
    expect(mockedGetTransactions).toHaveBeenCalledWith("1111111111111111", { limit: 20, cursor: undefined });
  });

  it("loads and appends the next page when the sentinel scrolls into view", async () => {
    mockedGetTransactions
      .mockResolvedValueOnce({ items: [transaction("t1")], next_cursor: "cursor-1" })
      .mockResolvedValueOnce({ items: [transaction("t2")], next_cursor: null });

    render(<TransactionsPanel accountNumber="1111111111111111" currencyCode="USD" />);
    await waitFor(() => expect(FakeIntersectionObserver.instances.length).toBeGreaterThan(0));

    act(() => {
      FakeIntersectionObserver.instances[0]!.trigger(true);
    });

    await waitFor(() => expect(mockedGetTransactions).toHaveBeenCalledTimes(2));
    expect(mockedGetTransactions).toHaveBeenNthCalledWith(2, "1111111111111111", {
      limit: 20, cursor: "cursor-1",
    });
  });

  it("stops requesting more once next_cursor is null", async () => {
    mockedGetTransactions.mockResolvedValue({ items: [transaction("t1")], next_cursor: null });

    render(<TransactionsPanel accountNumber="1111111111111111" currencyCode="USD" />);
    await waitFor(() => expect(mockedGetTransactions).toHaveBeenCalledTimes(1));

    expect(FakeIntersectionObserver.instances.every((o) => o.observed.length === 0)).toBe(true);
  });

  it("refetches from scratch when the account number changes", async () => {
    mockedGetTransactions.mockResolvedValue({ items: [transaction("t1")], next_cursor: null });

    const { rerender } = render(<TransactionsPanel accountNumber="1111111111111111" currencyCode="USD" />);
    await waitFor(() => expect(mockedGetTransactions).toHaveBeenCalledTimes(1));

    rerender(<TransactionsPanel accountNumber="2222222222222222" currencyCode="EUR" />);

    await waitFor(() => expect(mockedGetTransactions).toHaveBeenCalledTimes(2));
    expect(mockedGetTransactions).toHaveBeenNthCalledWith(2, "2222222222222222", { limit: 20, cursor: undefined });
  });

  it("shows the error message and never a stuck loading state on failure", async () => {
    mockedGetTransactions.mockRejectedValue(new Error("gateway unreachable"));

    render(<TransactionsPanel accountNumber="1111111111111111" currencyCode="USD" />);

    expect(await screen.findByText("gateway unreachable")).toBeInTheDocument();
    expect(screen.queryByText("Loading transactions…")).not.toBeInTheDocument();
  });
});
