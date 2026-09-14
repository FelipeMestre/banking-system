import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setAccessTokenGetter } from "@/lib/api/client";
import { CardAccountsList } from "@/features/card-account-admin/components/CardAccountsList";

const CARD_ACCOUNT = {
  id: "ca-1",
  customer_id: "c-1",
  paying_account_id: "acc-1",
  credit_limit: "5000.00",
  status: "active" as const,
};

const CARD = {
  id: "card-1",
  card_account_id: "ca-1",
  card_number: "•••• •••• •••• 1234",
  expiration_date: "2030-01-01",
  status: "active" as const,
};

function pageResponse(items: unknown[], total: number, offset = 0) {
  return new Response(JSON.stringify({ items, total, limit: 10, offset }), { status: 200 });
}

describe("CardAccountsList", () => {
  afterEach(() => {
    setAccessTokenGetter(null);
    vi.restoreAllMocks();
  });

  it("renders card accounts for the given customer", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      pageResponse([{ card_account: CARD_ACCOUNT, card: CARD }], 1),
    );

    render(<CardAccountsList customerId="c-1" hasWriteAdmin={true} />);

    expect(await screen.findByText("ca-1")).toBeInTheDocument();
    expect(screen.getByText("•••• •••• •••• 1234")).toBeInTheDocument();
    expect(screen.getByText("5000.00")).toBeInTheDocument();
  });

  it("shows an empty state when there are no card accounts", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(pageResponse([], 0));

    render(<CardAccountsList customerId="c-1" hasWriteAdmin={true} />);

    expect(await screen.findByText("No card accounts to show.")).toBeInTheDocument();
  });

  it("paginates via Previous/Next", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      pageResponse([{ card_account: CARD_ACCOUNT, card: CARD }], 25),
    );

    render(<CardAccountsList customerId="c-1" hasWriteAdmin={true} />);

    await screen.findByText("ca-1");
    expect(screen.getByText(/Showing 1–10 of 25/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      const lastUrl = String(fetchSpy.mock.calls.at(-1)?.[0]);
      expect(lastUrl).toContain("offset=10");
    });
  });

  it("refetches with the status query param when the filter changes", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      pageResponse([{ card_account: CARD_ACCOUNT, card: CARD }], 1),
    );

    render(<CardAccountsList customerId="c-1" hasWriteAdmin={true} />);
    await screen.findByText("ca-1");

    fireEvent.click(screen.getByRole("combobox", { name: /filter by status/i }));
    const blockedOption = await screen.findByRole("option", { name: "blocked" });
    fireEvent.click(blockedOption);

    await waitFor(() => {
      const lastUrl = String(fetchSpy.mock.calls.at(-1)?.[0]);
      expect(lastUrl).toContain("status=blocked");
    });
  });

  it("disables mutation buttons when the caller lacks write:admin", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      pageResponse([{ card_account: CARD_ACCOUNT, card: CARD }], 1),
    );

    render(<CardAccountsList customerId="c-1" hasWriteAdmin={false} />);

    await screen.findByText("ca-1");

    expect(screen.getByRole("button", { name: "Issue card account" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Update limit" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Block account" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Renew card" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Block card" })).toBeDisabled();
  });

  it("enables mutation buttons when the caller has write:admin", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      pageResponse([{ card_account: CARD_ACCOUNT, card: CARD }], 1),
    );

    render(<CardAccountsList customerId="c-1" hasWriteAdmin={true} />);

    await screen.findByText("ca-1");

    expect(screen.getByRole("button", { name: "Issue card account" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Update limit" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Block account" })).toBeEnabled();
  });

  it("only offers actions valid for the account's current status", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      pageResponse([{ card_account: { ...CARD_ACCOUNT, status: "closed" as const }, card: null }], 1),
    );

    render(<CardAccountsList customerId="c-1" hasWriteAdmin={true} />);

    await screen.findByText("ca-1");

    expect(screen.queryByRole("button", { name: "Block account" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Unblock account" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Renew card" })).toBeDisabled();
  });
});
