import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CreditCardsPageScreen } from "@/features/credit-cards/components/CreditCardsPageScreen";
import * as customerModule from "@/features/credit-cards/api/get-current-customer";
import * as cardAccountsModule from "@/features/credit-cards/api/get-card-accounts";
import * as movementsModule from "@/features/credit-cards/api/get-movements";
import * as statementsModule from "@/features/credit-cards/api/get-statements";
import * as payoffModule from "@/features/credit-cards/api/get-installment-payoff";
import * as requestPaymentModule from "@/features/credit-cards/api/request-payment";
import * as watchModule from "@/features/credit-cards/api/watch-payment-status";
import type { CardAccountListItem } from "@/features/credit-cards/types";
import type { Page } from "@/lib/api/types";

const CARD_ACCOUNTS_PAGE: Page<CardAccountListItem> = {
  items: [
    {
      card_account: { id: "ca-1", customer_id: "cust-1", paying_account_id: "a1", credit_limit: "1500.00", status: "active", used_credit: 15000 },
      card: { id: "card-1", card_account_id: "ca-1", card_number: "•••• •••• •••• 1234", expiration_date: "2029-01-01", status: "active" },
    },
    {
      card_account: { id: "ca-2", customer_id: "cust-1", paying_account_id: "a1", credit_limit: "500.00", status: "active", used_credit: 0 },
      card: { id: "card-2", card_account_id: "ca-2", card_number: "•••• •••• •••• 5678", expiration_date: "2027-06-01", status: "active" },
    },
  ],
  total: 2, limit: 50, offset: 0,
};

describe("CreditCardsPageScreen", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows both of the customer's cards once loaded", async () => {
    vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
    vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue(CARD_ACCOUNTS_PAGE);
    vi.spyOn(movementsModule, "getMovements").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    vi.spyOn(statementsModule, "getStatements").mockResolvedValue([]);
    vi.spyOn(payoffModule, "getInstallmentPayoff").mockResolvedValue({
      card_account_id: "ca-1", payoff_amount: "0.00", currency: "USD",
    });

    render(<CreditCardsPageScreen />);

    expect(await screen.findByText("•••• •••• •••• 1234")).toBeInTheDocument();
    expect(screen.getByText("•••• •••• •••• 5678")).toBeInTheDocument();
    expect(await screen.findByText("$150.00")).toBeInTheDocument();
    expect(screen.getByText("$1,350.00")).toBeInTheDocument();
  });

  /**
   * `credit-card-monthly-batch-statements` deliberately supersedes the prior
   * phase's "Explicit Exclusion of Phase-4 Billing UI" decision — statement
   * data now belongs on this page. What remains permanently out of scope is
   * admin-only card *management* (issue/renew/block), which stays a
   * Phase-1 CRUD concern this customer-facing page never exposes.
   */
  it("still renders none of the admin-only card management actions", async () => {
    vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
    vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue(CARD_ACCOUNTS_PAGE);
    vi.spyOn(movementsModule, "getMovements").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    vi.spyOn(statementsModule, "getStatements").mockResolvedValue([]);
    vi.spyOn(payoffModule, "getInstallmentPayoff").mockResolvedValue({
      card_account_id: "ca-1", payoff_amount: "0.00", currency: "USD",
    });

    render(<CreditCardsPageScreen />);
    await screen.findByText("•••• •••• •••• 1234");

    for (const forbidden of [/renew card/i, /block card/i, /issue card/i, /coming soon/i]) {
      expect(screen.queryByText(forbidden)).not.toBeInTheDocument();
    }
  });

  it("refreshes the movements list once a payment is approved, not just the card balance", async () => {
    vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
    vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue(CARD_ACCOUNTS_PAGE);
    vi.spyOn(movementsModule, "getMovements").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    vi.spyOn(statementsModule, "getStatements").mockResolvedValue([]);
    vi.spyOn(payoffModule, "getInstallmentPayoff").mockResolvedValue({
      card_account_id: "ca-1", payoff_amount: "0.00", currency: "USD",
    });
    vi.spyOn(requestPaymentModule, "requestPayment").mockResolvedValue({ request_id: "r1", status: "pending" });
    let deliverApproved: (() => void) | undefined;
    vi.spyOn(watchModule, "watchPaymentStatus").mockImplementation((_requestId, watcher) => {
      deliverApproved = () => watcher.onStatus({ request_id: "r1", status: "approved" });
      return () => {};
    });

    render(<CreditCardsPageScreen />);
    await screen.findByText("•••• •••• •••• 1234");
    await waitFor(() => expect(movementsModule.getMovements).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "Pay" }));
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));
    await screen.findByText("pending");

    act(() => deliverApproved?.());

    await waitFor(() => expect(movementsModule.getMovements).toHaveBeenCalledTimes(2));
  });

  it("refreshes movements a second time shortly after approval, to catch the async movement-consumer write", async () => {
    vi.useFakeTimers();
    try {
      vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
      vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue(CARD_ACCOUNTS_PAGE);
      vi.spyOn(movementsModule, "getMovements").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
      vi.spyOn(statementsModule, "getStatements").mockResolvedValue([]);
      vi.spyOn(payoffModule, "getInstallmentPayoff").mockResolvedValue({
        card_account_id: "ca-1", payoff_amount: "0.00", currency: "USD",
      });
      vi.spyOn(requestPaymentModule, "requestPayment").mockResolvedValue({ request_id: "r1", status: "pending" });
      let deliverApproved: (() => void) | undefined;
      vi.spyOn(watchModule, "watchPaymentStatus").mockImplementation((_requestId, watcher) => {
        deliverApproved = () => watcher.onStatus({ request_id: "r1", status: "approved" });
        return () => {};
      });

      render(<CreditCardsPageScreen />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      await vi.waitFor(() => expect(screen.getByText("•••• •••• •••• 1234")).toBeInTheDocument());
      await vi.waitFor(() => expect(movementsModule.getMovements).toHaveBeenCalledTimes(1));

      fireEvent.click(screen.getByRole("button", { name: "Pay" }));
      fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });
      fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      act(() => deliverApproved?.());
      await vi.waitFor(() => expect(movementsModule.getMovements).toHaveBeenCalledTimes(2));

      expect(movementsModule.getMovements).toHaveBeenCalledTimes(2);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500);
      });

      expect(movementsModule.getMovements).toHaveBeenCalledTimes(3);
    } finally {
      vi.useRealTimers();
    }
  });

  it("dual-refetches card-accounts on PayDialog approved: 2x immediate, 3x after 1500ms", async () => {
    vi.useFakeTimers();
    try {
      vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
      const getCardAccountsSpy = vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue(CARD_ACCOUNTS_PAGE);
      vi.spyOn(movementsModule, "getMovements").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
      vi.spyOn(statementsModule, "getStatements").mockResolvedValue([]);
      vi.spyOn(payoffModule, "getInstallmentPayoff").mockResolvedValue({
        card_account_id: "ca-1", payoff_amount: "0.00", currency: "USD",
      });
      vi.spyOn(requestPaymentModule, "requestPayment").mockResolvedValue({ request_id: "r1", status: "pending" });
      let deliverApproved: (() => void) | undefined;
      vi.spyOn(watchModule, "watchPaymentStatus").mockImplementation((_requestId, watcher) => {
        deliverApproved = () => watcher.onStatus({ request_id: "r1", status: "approved" });
        return () => {};
      });

      render(<CreditCardsPageScreen />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      await vi.waitFor(() => expect(screen.getByText("•••• •••• •••• 1234")).toBeInTheDocument());
      expect(getCardAccountsSpy).toHaveBeenCalledTimes(1);

      fireEvent.click(screen.getByRole("button", { name: "Pay" }));
      fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });
      fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      act(() => deliverApproved?.());
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      expect(getCardAccountsSpy).toHaveBeenCalledTimes(2);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500);
      });

      expect(getCardAccountsSpy).toHaveBeenCalledTimes(3);
    } finally {
      vi.useRealTimers();
    }
  });

  it("prevents card-accounts timer stacking on rapid second approved", async () => {
    vi.useFakeTimers();
    try {
      vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
      const getCardAccountsSpy = vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue(CARD_ACCOUNTS_PAGE);
      vi.spyOn(movementsModule, "getMovements").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
      vi.spyOn(statementsModule, "getStatements").mockResolvedValue([]);
      vi.spyOn(payoffModule, "getInstallmentPayoff").mockResolvedValue({
        card_account_id: "ca-1", payoff_amount: "0.00", currency: "USD",
      });
      vi.spyOn(requestPaymentModule, "requestPayment").mockResolvedValue({ request_id: "r1", status: "pending" });
      let deliverApproved: (() => void) | undefined;
      vi.spyOn(watchModule, "watchPaymentStatus").mockImplementation((_requestId, watcher) => {
        deliverApproved = () => watcher.onStatus({ request_id: "r1", status: "approved" });
        return () => {};
      });

      render(<CreditCardsPageScreen />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      await vi.waitFor(() => expect(screen.getByText("•••• •••• •••• 1234")).toBeInTheDocument());

      fireEvent.click(screen.getByRole("button", { name: "Pay" }));
      fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });
      fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      act(() => deliverApproved?.());
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(getCardAccountsSpy).toHaveBeenCalledTimes(2);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(700);
      });
      expect(getCardAccountsSpy).toHaveBeenCalledTimes(2);
      act(() => deliverApproved?.());
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(getCardAccountsSpy).toHaveBeenCalledTimes(3);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500);
      });
      expect(getCardAccountsSpy).toHaveBeenCalledTimes(4);
    } finally {
      vi.useRealTimers();
    }
  });

  it("clears pending card-accounts timer on unmount", async () => {
    vi.useFakeTimers();
    try {
      vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
      const getCardAccountsSpy = vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue(CARD_ACCOUNTS_PAGE);
      vi.spyOn(movementsModule, "getMovements").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
      vi.spyOn(statementsModule, "getStatements").mockResolvedValue([]);
      vi.spyOn(payoffModule, "getInstallmentPayoff").mockResolvedValue({
        card_account_id: "ca-1", payoff_amount: "0.00", currency: "USD",
      });
      vi.spyOn(requestPaymentModule, "requestPayment").mockResolvedValue({ request_id: "r1", status: "pending" });
      let deliverApproved: (() => void) | undefined;
      vi.spyOn(watchModule, "watchPaymentStatus").mockImplementation((_requestId, watcher) => {
        deliverApproved = () => watcher.onStatus({ request_id: "r1", status: "approved" });
        return () => {};
      });

      const { unmount } = render(<CreditCardsPageScreen />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      await vi.waitFor(() => expect(screen.getByText("•••• •••• •••• 1234")).toBeInTheDocument());

      fireEvent.click(screen.getByRole("button", { name: "Pay" }));
      fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100.00" } });
      fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      act(() => deliverApproved?.());
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(getCardAccountsSpy).toHaveBeenCalledTimes(2);

      unmount();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500);
      });
      expect(getCardAccountsSpy).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps display at last used_credit until refetch and never does optimistic subtraction", async () => {
    vi.useFakeTimers();
    try {
      vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
      vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue(CARD_ACCOUNTS_PAGE);
      vi.spyOn(movementsModule, "getMovements").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
      vi.spyOn(statementsModule, "getStatements").mockResolvedValue([]);
      vi.spyOn(payoffModule, "getInstallmentPayoff").mockResolvedValue({
        card_account_id: "ca-1", payoff_amount: "0.00", currency: "USD",
      });
      vi.spyOn(requestPaymentModule, "requestPayment").mockResolvedValue({ request_id: "r1", status: "pending" });
      let deliverApproved: (() => void) | undefined;
      vi.spyOn(watchModule, "watchPaymentStatus").mockImplementation((_requestId, watcher) => {
        deliverApproved = () => watcher.onStatus({ request_id: "r1", status: "approved" });
        return () => {};
      });

      render(<CreditCardsPageScreen />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      await vi.waitFor(() => expect(screen.getByText("$150.00")).toBeInTheDocument());
      expect(screen.getByText("$1,350.00")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Pay" }));
      fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "50.00" } });
      fireEvent.click(screen.getByRole("button", { name: "Submit payment" }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      act(() => deliverApproved?.());
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      expect(screen.getByText("$150.00")).toBeInTheDocument();
      expect(screen.getByText("$1,350.00")).toBeInTheDocument();
      expect(screen.queryByText("$100.00")).not.toBeInTheDocument();
      expect(screen.getByText("Updating…")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("renders the movements list inside a fixed-height scroll container, not an unbounded page-growing list", async () => {
    vi.spyOn(customerModule, "getCurrentCustomer").mockResolvedValue({ id: "cust-1" });
    vi.spyOn(cardAccountsModule, "getCardAccounts").mockResolvedValue(CARD_ACCOUNTS_PAGE);
    vi.spyOn(movementsModule, "getMovements").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    vi.spyOn(statementsModule, "getStatements").mockResolvedValue([]);
    vi.spyOn(payoffModule, "getInstallmentPayoff").mockResolvedValue({
      card_account_id: "ca-1", payoff_amount: "0.00", currency: "USD",
    });

    render(<CreditCardsPageScreen />);
    await screen.findByText("•••• •••• •••• 1234");

    const container = screen.getByTestId("movements-scroll-container");
    expect(container.className).toContain("overflow-y-auto");
    expect(container.className).toContain("max-h-[160px]");
    expect(container.className).toContain("sm:max-h-[190px]");
    expect(container.className).toContain("lg:max-h-[220px]");
  });
});
