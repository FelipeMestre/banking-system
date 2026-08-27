"use client";

import { useEffect, useState } from "react";
import { getLocations } from "../api/get-locations";
import type { Location } from "../types";

const PAGE_SIZE = 10;

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; items: Location[]; total: number };

export function LocationsList() {
  const [offset, setOffset] = useState(0);
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    getLocations({ limit: PAGE_SIZE, offset })
      .then((page) => {
        if (!cancelled) setState({ kind: "ready", items: page.items, total: page.total });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "Could not load locations.",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [offset]);

  if (state.kind === "loading") {
    return <p className="subtitle">Loading locations…</p>;
  }

  if (state.kind === "error") {
    return <p className="subtitle">{state.message}</p>;
  }

  const { items, total } = state;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);
  const canPrev = offset > 0;
  const canNext = to < total;

  return (
    <div className="flex flex-col gap-ds-3">
      <div className="overflow-x-auto border-2 border-divider">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={2} className="text-neutral-600">
                  No locations to show.
                </td>
              </tr>
            ) : (
              items.map((location) => (
                <tr key={location.id}>
                  <td className="font-mono text-xs">{location.id}</td>
                  <td>{location.name}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-neutral-600">
          {total === 0 ? "No locations" : `Showing ${from}–${to} of ${total}`}
        </span>
        <div className="flex gap-ds-2">
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!canPrev}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!canNext}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
