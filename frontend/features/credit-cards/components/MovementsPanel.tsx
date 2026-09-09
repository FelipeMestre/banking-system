"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getMovements } from "../api/get-movements";
import { MovementsList } from "./MovementsList";
import type { CardMovement } from "../types";

interface Props {
  cardAccountId: string;
  statementId?: string;
}

const PAGE_SIZE = 20;

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; items: CardMovement[]; total: number };

/**
 * Infinite-scroll wrapper around the pure, presentational `MovementsList`.
 *
 * Owns pagination itself, separately from `CreditCardsPageScreen`'s own
 * movements fetch (which feeds `StatementTotalsSidebar`'s "Payments made"
 * total): that total is shown as a single, immediately-final figure, so it
 * must never depend on how far someone has scrolled this list. Two fetches
 * of overlapping data is the deliberate trade for that — see the totals
 * sidebar's own docstring on why its figures are never re-derived from a
 * partial movements list.
 *
 * The scroll container's height is fixed at any given breakpoint (that's
 * what makes this "infinite scroll" instead of the page itself growing
 * without bound) but the fixed value itself changes across breakpoints via
 * Tailwind's responsive `max-h-*` variants, rather than one height for
 * every screen size.
 */
export function MovementsPanel({ cardAccountId, statementId }: Props) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [loadingMore, setLoadingMore] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const loadPage = useCallback(
    (offset: number, append: boolean) => {
      if (!append) setState({ kind: "loading" });
      getMovements({ cardAccountId, limit: PAGE_SIZE, offset, statementId })
        .then((page) => {
          setState((current) => ({
            kind: "ready",
            items: append && current.kind === "ready" ? [...current.items, ...page.items] : page.items,
            total: page.total,
          }));
        })
        .catch((error: unknown) => {
          if (!append) {
            setState({
              kind: "error",
              message: error instanceof Error ? error.message : "Could not load movements.",
            });
          }
        })
        .finally(() => setLoadingMore(false));
    },
    [cardAccountId, statementId],
  );

  useEffect(() => {
    loadPage(0, false);
  }, [loadPage]);

  const items = state.kind === "ready" ? state.items : [];
  const hasMore = state.kind === "ready" && items.length < state.total;

  useEffect(() => {
    if (!hasMore || loadingMore) return;
    const sentinel = sentinelRef.current;
    const root = scrollRef.current;
    if (!sentinel || !root) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setLoadingMore(true);
          loadPage(items.length, true);
        }
      },
      { root, threshold: 0.1 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadingMore, loadPage, items.length]);

  if (state.kind === "loading") {
    return <p className="m-0 text-sm text-neutral-600">Loading movements…</p>;
  }

  if (state.kind === "error") {
    return <p className="m-0 text-sm text-neutral-600">{state.message}</p>;
  }

  return (
    <div
      ref={scrollRef}
      data-testid="movements-scroll-container"
      className="max-h-[160px] overflow-y-auto pr-ds-1 sm:max-h-[190px] lg:max-h-[220px]"
    >
      <MovementsList items={items} />
      {hasMore ? (
        <div ref={sentinelRef} className="py-ds-2 text-center text-xs text-neutral-500" aria-hidden={!loadingMore}>
          {loadingMore ? "Loading more…" : ""}
        </div>
      ) : null}
    </div>
  );
}
