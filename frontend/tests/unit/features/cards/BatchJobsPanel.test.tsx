import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BatchJobsPanel } from "@/features/cards/components/BatchJobsPanel";
import * as monthlyCloseModule from "@/features/cards/api/run-monthly-close";
import * as dueDateCheckModule from "@/features/cards/api/run-due-date-check";

describe("BatchJobsPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("runs the monthly-close job and reports how many statements closed", async () => {
    vi.spyOn(monthlyCloseModule, "runMonthlyClose").mockResolvedValue({
      closed_count: 2, statement_ids: ["s1", "s2"], card_account_ids: ["ca-1", "ca-2"],
    });

    render(<BatchJobsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Run monthly close check" }));

    expect(await screen.findByText("Closed 2 statements.")).toBeInTheDocument();
  });

  it("reports a no-op result when nothing was due to close", async () => {
    vi.spyOn(monthlyCloseModule, "runMonthlyClose").mockResolvedValue({
      closed_count: 0, statement_ids: [], card_account_ids: [],
    });

    render(<BatchJobsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Run monthly close check" }));

    expect(await screen.findByText("No account was due to close.")).toBeInTheDocument();
  });

  it("runs the due-date check job and reports finalized statements plus late fees", async () => {
    vi.spyOn(dueDateCheckModule, "runDueDateCheck").mockResolvedValue({
      finalized_count: 3, late_fees_applied_count: 1,
    });

    render(<BatchJobsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Run due-date check" }));

    expect(await screen.findByText("Finalized 3 statements, applied 1 late fee.")).toBeInTheDocument();
  });

  it("shows an error message when the job fails", async () => {
    vi.spyOn(monthlyCloseModule, "runMonthlyClose").mockRejectedValue(new Error("The gateway is down."));

    render(<BatchJobsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Run monthly close check" }));

    await waitFor(() => expect(screen.getByText("The gateway is down.")).toBeInTheDocument());
  });
});
