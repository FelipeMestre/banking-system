import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NoAccountsEmptyState } from "@/features/accounts/components/NoAccountsEmptyState";

describe("NoAccountsEmptyState", () => {
  it("renders the headline, body copy, and the create-account CTA", () => {
    render(<NoAccountsEmptyState onCreateClick={vi.fn()} />);

    expect(screen.getByText("You don't have any accounts yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create an account" })).toBeInTheDocument();
  });

  it("fires onCreateClick when the CTA is activated", () => {
    const onCreateClick = vi.fn();
    render(<NoAccountsEmptyState onCreateClick={onCreateClick} />);

    fireEvent.click(screen.getByRole("button", { name: "Create an account" }));

    expect(onCreateClick).toHaveBeenCalledTimes(1);
  });
});
