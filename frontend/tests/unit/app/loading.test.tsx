import { act, render, screen } from "@testing-library/react";
import { Suspense } from "react";
import { describe, expect, it } from "vitest";
import Loading from "@/app/loading";

describe("app/loading.tsx", () => {
  it("default export renders LoadingScreen with status role", () => {
    render(<Loading />);
    const status = screen.getByRole("status");
    expect(status).toBeInTheDocument();
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveAttribute("data-slot", "loading-screen");
  });

  it("renders fallback while suspended then child after resolve", async () => {
    let resolve!: () => void;
    const promise = new Promise<void>((res) => {
      resolve = res;
    });
    let shouldSuspend = true;

    function SuspendingChild() {
      if (shouldSuspend) throw promise;
      return <div>child ready</div>;
    }

    render(
      <Suspense fallback={<Loading />}>
        <SuspendingChild />
      </Suspense>
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getAllByText("Loading your accounts securely").length).toBeGreaterThanOrEqual(1);

    await act(async () => {
      shouldSuspend = false;
      resolve();
      await promise;
    });

    expect(await screen.findByText("child ready")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("is not a progressbar and has no aria-valuenow", () => {
    render(<Loading />);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).not.toHaveAttribute("aria-valuenow");
  });

  it("has no focus trap", () => {
    render(<Loading />);
    const status = screen.getByRole("status");
    expect(status).not.toHaveAttribute("tabIndex");
  });

  it("has polite aria-live and busy true", () => {
    render(<Loading />);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveAttribute("aria-busy", "true");
  });
});
