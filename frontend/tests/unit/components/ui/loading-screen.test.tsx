import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LoadingScreen } from "@/components/ui/loading-screen";

describe("LoadingScreen", () => {
  it("renders with role=status aria-live polite and aria-busy", () => {
    render(<LoadingScreen />);
    const status = screen.getByRole("status");
    expect(status).toBeInTheDocument();
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading your accounts securely");
  });

  it("renders default message and sr-only text", () => {
    render(<LoadingScreen />);
    expect(screen.getAllByText("Loading your accounts securely").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("status")).toHaveTextContent("Loading your accounts securely");
    // sr-only span also contains same text; visible text + sr-only both present
    const hidden = document.querySelector(".sr-only");
    expect(hidden).not.toBeNull();
    expect(hidden?.textContent).toBe("Loading your accounts securely");
  });

  it("renders custom message when provided", () => {
    render(<LoadingScreen message="Please wait" />);
    expect(screen.getAllByText("Please wait").length).toBeGreaterThanOrEqual(1);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-label", "Please wait");
    expect(status).toHaveTextContent("Please wait");
  });

  it("has data-slot loading-screen", () => {
    render(<LoadingScreen />);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("data-slot", "loading-screen");
  });

  it("supports data-testid", () => {
    render(<LoadingScreen data-testid="loading-screen" />);
    expect(screen.getByTestId("loading-screen")).toBeInTheDocument();
  });

  it("fullScreen true renders min-h-screen, false renders min-h-[240px]", () => {
    const { rerender } = render(<LoadingScreen fullScreen />);
    expect(screen.getByRole("status")).toHaveClass("min-h-screen");

    rerender(<LoadingScreen fullScreen={false} />);
    expect(screen.getByRole("status")).toHaveClass("min-h-[240px]");
  });

  it("spinner has border accent and ob-spin animation and aria-hidden", () => {
    render(<LoadingScreen />);
    const status = screen.getByRole("status");
    // spinner is element with aria-hidden inside status
    const hiddenElements = status.querySelectorAll('[aria-hidden="true"]');
    expect(hiddenElements.length).toBeGreaterThanOrEqual(2);
    // find spinner by its classes
    const spinner = Array.from(hiddenElements).find((el) =>
      el.className.includes("border-t-accent")
    );
    expect(spinner).toBeDefined();
    expect(spinner?.className).toContain("border-[3px]");
    expect(spinner?.className).toContain("border-neutral-300");
    expect(spinner?.className).toContain("border-t-accent");
    expect(spinner?.className).toContain("ob-spin");
  });

  it("bar fill has w-[30%] bg-accent and ob-sweep animation and aria-hidden", () => {
    render(<LoadingScreen />);
    const status = screen.getByRole("status");
    const fill = status.querySelector(".bg-accent.w-\\[30\\%\\]") || status.querySelector('[class*="w-[30%]"]');
    // fallback: query by class containing w-[30%]
    const sweepEl = Array.from(status.querySelectorAll("*")).find(
      (el) => el.className.includes("w-[30%]") && el.className.includes("bg-accent")
    );
    expect(sweepEl).toBeDefined();
    expect(sweepEl?.className).toContain("w-[30%]");
    expect(sweepEl?.className).toContain("bg-accent");
    expect(sweepEl?.className).toContain("ob-sweep");
    expect(sweepEl?.getAttribute("aria-hidden")).toBe("true");
  });

  it("container has ob-fade-in animation", () => {
    render(<LoadingScreen />);
    const status = screen.getByRole("status");
    expect(status.className).toContain("ob-fade-in");
  });

  it("uses Modernist tokens and ds-* scale without inline style", () => {
    const { container } = render(<LoadingScreen />);
    const status = screen.getByRole("status");
    expect(status.className).toContain("bg-bg");
    expect(status.className).toContain("gap-ds-3");
    expect(status.className).toContain("p-ds-8");
    // ensure no inline style prop on status or spinner
    expect(status.getAttribute("style")).toBeNull();
    const spinner = container.querySelector('[aria-hidden="true"]');
    expect(spinner?.getAttribute("style")).toBeNull();
  });

  it("renders OpenBank logo with accent square and wordmark", () => {
    render(<LoadingScreen />);
    const status = screen.getByRole("status");
    const square = status.querySelector(".bg-accent.w-3\\.5") || Array.from(status.querySelectorAll("*")).find((el) => el.className.includes("w-3.5") && el.className.includes("bg-accent"));
    expect(square).toBeDefined();
    expect(square?.className).toContain("h-3.5");
    expect(square?.className).toContain("w-3.5");
    expect(square?.className).toContain("rounded-none");
    expect(screen.getByText("OpenBank")).toBeInTheDocument();
  });

  it("is not a progressbar and has no aria-valuenow", () => {
    render(<LoadingScreen />);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    const status = screen.getByRole("status");
    expect(status).not.toHaveAttribute("aria-valuenow");
  });

  it("does not trap focus", () => {
    render(<LoadingScreen />);
    const status = screen.getByRole("status");
    expect(status).not.toHaveAttribute("tabIndex");
  });
});
