import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MovementsPanel } from "@/features/credit-cards/components/MovementsPanel";
import { getMovements } from "@/features/credit-cards/api/get-movements";
import type { CardMovement } from "@/features/credit-cards/types";

vi.mock("@/features/credit-cards/api/get-movements", () => ({ getMovements: vi.fn() }));

const mockedGetMovements = vi.mocked(getMovements);

/** A controllable stand-in for jsdom's missing IntersectionObserver: records
 * the callback it was constructed with so a test can fire it manually, as
 * the real one would when the sentinel scrolls into view. */
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

function movement(id: string): CardMovement {
  return { id, movement_type: "purchase", amount: "10.00", currency: "USD", occurred_at: "2026-09-04T00:00:00Z" };
}

describe("MovementsPanel", () => {
  beforeEach(() => {
    FakeIntersectionObserver.instances = [];
    vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders the first page inside a fixed-height, responsive scroll container", async () => {
    mockedGetMovements.mockResolvedValue({ items: [movement("m1")], total: 1, limit: 20, offset: 0 });

    render(<MovementsPanel cardAccountId="card-1" />);

    await waitFor(() => expect(screen.getByTestId("movements-scroll-container")).toBeInTheDocument());
    const container = screen.getByTestId("movements-scroll-container");
    expect(container.className).toContain("overflow-y-auto");
    expect(container.className).toContain("max-h-[160px]");
    expect(container.className).toContain("sm:max-h-[190px]");
    expect(container.className).toContain("lg:max-h-[220px]");
    expect(mockedGetMovements).toHaveBeenCalledWith({
      cardAccountId: "card-1", limit: 20, offset: 0, statementId: undefined,
    });
  });

  it("loads and appends the next page when the sentinel scrolls into view", async () => {
    mockedGetMovements
      .mockResolvedValueOnce({ items: [movement("m1")], total: 2, limit: 20, offset: 0 })
      .mockResolvedValueOnce({ items: [movement("m2")], total: 2, limit: 20, offset: 1 });

    render(<MovementsPanel cardAccountId="card-1" />);
    await waitFor(() => expect(FakeIntersectionObserver.instances.length).toBeGreaterThan(0));

    act(() => {
      FakeIntersectionObserver.instances[0]!.trigger(true);
    });

    await waitFor(() => expect(mockedGetMovements).toHaveBeenCalledTimes(2));
    expect(mockedGetMovements).toHaveBeenNthCalledWith(2, {
      cardAccountId: "card-1", limit: 20, offset: 1, statementId: undefined,
    });
  });

  it("stops requesting more once every movement has been loaded", async () => {
    mockedGetMovements.mockResolvedValue({ items: [movement("m1")], total: 1, limit: 20, offset: 0 });

    render(<MovementsPanel cardAccountId="card-1" />);
    await waitFor(() => expect(mockedGetMovements).toHaveBeenCalledTimes(1));

    // total === items.length -> no sentinel should even be mounted to observe.
    expect(FakeIntersectionObserver.instances.every((o) => o.observed.length === 0)).toBe(true);
  });

  it("passes statementId through to every page request", async () => {
    mockedGetMovements.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

    render(<MovementsPanel cardAccountId="card-1" statementId="stmt-1" />);

    await waitFor(() =>
      expect(mockedGetMovements).toHaveBeenCalledWith({
        cardAccountId: "card-1", limit: 20, offset: 0, statementId: "stmt-1",
      }),
    );
  });

  it("shows the error message and never a stuck loading state on failure", async () => {
    mockedGetMovements.mockRejectedValue(new Error("gateway unreachable"));

    render(<MovementsPanel cardAccountId="card-1" />);

    expect(await screen.findByText("gateway unreachable")).toBeInTheDocument();
    expect(screen.queryByText("Loading movements…")).not.toBeInTheDocument();
  });
});
