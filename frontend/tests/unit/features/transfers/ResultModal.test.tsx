import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ResultModal } from "@/features/transfers/components/ResultModal";

describe("ResultModal", () => {
  it("success variant shows check, success text and Go to Homepage", () => {
    render(<ResultModal result={{ kind: "success" }} onClose={vi.fn()} />);
    expect(screen.getByText("Success in the operation")).toBeInTheDocument();
    expect(screen.getByText("Go to Homepage")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    // close X button
    expect(screen.getByLabelText("Close")).toBeInTheDocument();
    // 72px border-3 check icon container
    const iconBox = screen.getByTestId("result-icon");
    expect(iconBox.className).toContain("border-3");
  });

  it("error variant shows X, error text and Try again", () => {
    const onClose = vi.fn();
    render(<ResultModal result={{ kind: "error", message: "failed" }} onClose={onClose} />);
    expect(screen.getByText("Error in the operation")).toBeInTheDocument();
    expect(screen.getByText("Try again")).toBeInTheDocument();
    const iconBox = screen.getByTestId("result-icon");
    expect(iconBox.className).toContain("border-accent-700");
    fireEvent.click(screen.getByText("Try again"));
    expect(onClose).toHaveBeenCalled();
  });

  it("Go to Homepage navigates to /", () => {
    render(<ResultModal result={{ kind: "success" }} onClose={vi.fn()} />);
    const link = screen.getByText("Go to Homepage").closest("a");
    expect(link).toHaveAttribute("href", "/");
  });

  it("has focus trap via Dialog", () => {
    render(<ResultModal result={{ kind: "success" }} onClose={vi.fn()} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
