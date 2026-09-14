import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AccountsAndTransactions } from "@/components/home/AccountsAndTransactions";
import type { AccountSummary } from "@/features/accounts";

const ACCOUNTS: AccountSummary[] = [
  {
    id: "a1",
    account_number: "1111222233334444",
    currency: "USD",
    customer_id: "c1",
    balance: 458213,
    status: "active",
    label: "USD account",
  },
];

function mockTransactionsFetch() {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ items: [], next_cursor: null }), { status: 200 }),
  );
}

/**
 * `showDetails` is owned by the parent (`HomeDashboard`, via
 * `useAccountVisibility`) so the same toggle also masks `CreditCardPanel` —
 * this component is a pure controlled consumer of it. This harness plays the
 * parent's role for these tests; the hook's own persistence behavior
 * (localStorage, surviving a remount) is covered directly in
 * `useAccountVisibility.test.ts`, not duplicated here.
 */
function Harness({
  initialShowDetails = false,
  onSelectAccount = () => {},
}: {
  initialShowDetails?: boolean;
  onSelectAccount?: (accountNumber: string) => void;
}) {
  const [showDetails, setShowDetails] = useState(initialShowDetails);
  return (
    <AccountsAndTransactions
      accounts={ACCOUNTS}
      asOf="just now"
      selectedAccountNumber="1111222233334444"
      onSelectAccount={onSelectAccount}
      showDetails={showDetails}
      onToggleShowDetails={() => setShowDetails((current) => !current)}
      aside={null}
    />
  );
}

function renderScreen(props?: Parameters<typeof Harness>[0]) {
  return render(<Harness {...props} />);
}

describe("AccountsAndTransactions — account detail visibility", () => {
  beforeEach(() => {
    mockTransactionsFetch();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("hides the account number and balance by default", async () => {
    renderScreen();
    await waitFor(() => expect(screen.getByRole("button", { name: "Show account details" })).toBeInTheDocument());
    expect(screen.getByText("•••• ••••")).toBeInTheDocument();
    expect(screen.getByText("••••••")).toBeInTheDocument();
    expect(screen.queryByText("1111-2222-3333-4444")).not.toBeInTheDocument();
    expect(screen.queryByText("4,582.13")).not.toBeInTheDocument();
  });

  it("reveals the real account number and balance on click, and updates the button's label", async () => {
    renderScreen();
    const toggle = await screen.findByRole("button", { name: "Show account details" });

    fireEvent.click(toggle);

    expect(screen.getByText("1111-2222-3333-4444")).toBeInTheDocument();
    expect(screen.getByText("4,582.13")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hide account details" })).toBeInTheDocument();
    expect(screen.queryByText("•••• ••••")).not.toBeInTheDocument();
  });

  it("the icon reflects the CURRENT state, not the next action: open eye while visible, crossed-out while hidden", async () => {
    renderScreen();
    const hiddenToggle = await screen.findByRole("button", { name: "Show account details" });
    // Details are hidden right now — the icon must be the crossed-out eye.
    expect(hiddenToggle.querySelector("svg")?.getAttribute("class")).toContain("lucide-eye-off");

    fireEvent.click(hiddenToggle);

    const visibleToggle = screen.getByRole("button", { name: "Hide account details" });
    // Details are showing right now — the icon must be the plain, open eye.
    const icon = visibleToggle.querySelector("svg")?.getAttribute("class");
    expect(icon).toContain("lucide-eye");
    expect(icon).not.toContain("lucide-eye-off");
  });

  it("renders unmasked with the open-eye icon when the parent's showDetails prop starts true", async () => {
    renderScreen({ initialShowDetails: true });

    const toggle = await screen.findByRole("button", { name: "Hide account details" });
    const icon = toggle.querySelector("svg")?.getAttribute("class");
    expect(icon).toContain("lucide-eye");
    expect(icon).not.toContain("lucide-eye-off");
    expect(screen.getByText("1111-2222-3333-4444")).toBeInTheDocument();
  });
});

describe("AccountsAndTransactions — copy account number", () => {
  let writeText: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    mockTransactionsFetch();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is disabled while details are hidden, with a label explaining why", async () => {
    renderScreen();
    const copyButton = await screen.findByRole("button", { name: "Reveal the account number to copy it" });
    expect(copyButton).toBeDisabled();
  });

  it("copies the raw, unformatted account number — not the dash-grouped display string", async () => {
    renderScreen();
    const visibilityToggle = await screen.findByRole("button", { name: "Show account details" });
    fireEvent.click(visibilityToggle);

    const copyButton = await screen.findByRole("button", { name: "Copy account number" });
    fireEvent.click(copyButton);

    await waitFor(() => expect(writeText).toHaveBeenCalledWith("1111222233334444"));
  });

  it("clicking copy does not also select the account (event must not bubble)", async () => {
    const onSelectAccount = vi.fn();
    renderScreen({ onSelectAccount });

    const visibilityToggle = await screen.findByRole("button", { name: "Show account details" });
    fireEvent.click(visibilityToggle);

    const copyButton = await screen.findByRole("button", { name: "Copy account number" });
    fireEvent.click(copyButton);

    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(onSelectAccount).not.toHaveBeenCalled();
  });

  it("shows a confirmation icon after copying", async () => {
    renderScreen();
    const visibilityToggle = await screen.findByRole("button", { name: "Show account details" });
    fireEvent.click(visibilityToggle);

    const copyButton = await screen.findByRole("button", { name: "Copy account number" });
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(copyButton.querySelector("svg")?.getAttribute("class")).toContain("lucide-check");
    });
  });
});
