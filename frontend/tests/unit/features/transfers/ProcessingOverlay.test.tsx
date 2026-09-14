import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProcessingOverlay } from "@/features/transfers/components/ProcessingOverlay";

describe("ProcessingOverlay", () => {
  it("shows Processing your transfer with aria-busy when visible", () => {
    render(<ProcessingOverlay isLoading={true} />);
    expect(screen.getByText("Processing your transfer")).toBeInTheDocument();
    expect(screen.getByTestId("processing-overlay")).toHaveAttribute("aria-busy", "true");
  });

  it("is hidden when not loading", () => {
    const { container } = render(<ProcessingOverlay isLoading={false} />);
    expect(screen.queryByText("Processing your transfer")).not.toBeInTheDocument();
    expect(container.firstChild).toBeNull();
  });
});
