"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getTransactions } from "../api/get-transactions";
import { TransactionsList } from "./TransactionsList";
import type { Transaction } from "../types";

interface Props {
  accountNumber: string;
  currencyCode: string;
}

const PAGE_SIZE = 20;

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; items: Transaction[]; nextCursor: string | null };

/**
 * Infinite-scroll wrapper around the pure, presentational `TransactionsList`
 * — same split as credit cards' `MovementsPanel`/`MovementsList`. Owns
 * cursor-based pagination itself (the gateway's own pagination style here,
 * spec §3.3: opaque `next_cursor`, not limit/offset), fetching the next page
 * as a sentinel at the bottom of a fixed-height scroll container comes into
 * view.
 *
 * Resets and refetches only when `accountNumber` changes — reselecting the
 * same account keeps whatever is already loaded, the same effect the old
 * per-account cache in `HomeDashboard` used to provide.
 *
 * The scroll container's height is fixed at any given breakpoint (that's
 * what makes this "infinite scroll" instead of the page growing without
 * bound), but the fixed value itself changes across breakpoints rather than
 * being one height for every screen size.
 */
export function TransactionsPanel({ accountNumber, currencyCode }: Props) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [loadingMore, setLoadingMore] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const loadPage = useCallback(
    (cursor: string | undefined, append: boolean) => {
      if (!append) setState({ kind: "loading" });
      getTransactions(accountNumber, { limit: PAGE_SIZE, cursor })
        .then((page) => {
          setState((current) => ({
            kind: "ready",
            items: append && current.kind === "ready" ? [...current.items, ...page.items] : page.items,
            nextCursor: page.next_cursor,
          }));
        })
        .catch((error: unknown) => {
          if (!append) {
            setState({
              kind: "error",
              message: error instanceof Error ? error.message : "Could not load transactions.",
            });
          }
        })
        .finally(() => setLoadingMore(false));
    },
    [accountNumber],
  );

  useEffect(() => {
    loadPage(undefined, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-fetch when the account itself changes
  }, [accountNumber]);

  const items = state.kind === "ready" ? state.items : [];
  const hasMore = state.kind === "ready" && state.nextCursor !== null;

  useEffect(() => {
    if (!hasMore || loadingMore) return;
    const sentinel = sentinelRef.current;
    const root = scrollRef.current;
    if (!sentinel || !root) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && state.kind === "ready") {
          setLoadingMore(true);
          loadPage(state.nextCursor ?? undefined, true);
        }
      },
      { root, threshold: 0.1 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadingMore, loadPage, state]);

  if (state.kind === "loading") {
    return <p className="m-0 text-sm text-neutral-600">Loading transactions…</p>;
  }

  if (state.kind === "error") {
    return <p className="m-0 text-sm text-neutral-600">{state.message}</p>;
  }

  return (
    <div
      ref={scrollRef}
      data-testid="transactions-scroll-container"
      className="max-h-[140px] overflow-y-auto pr-ds-1 sm:max-h-[300px] lg:max-h-[400px]"
    >
      <TransactionsList transactions={items} currencyCode={currencyCode} />
      {hasMore ? (
        <div ref={sentinelRef} className="py-ds-2 text-center text-xs text-neutral-500" aria-hidden={!loadingMore}>
          {loadingMore ? "Loading more…" : ""}
        </div>
      ) : null}
    </div>
  );
}
