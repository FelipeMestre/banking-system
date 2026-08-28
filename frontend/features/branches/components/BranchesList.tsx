"use client";

import { useEffect, useState } from "react";
import { getBranches } from "../api/get-branches";
import type { Branch } from "../types";

const PAGE_SIZE = 10;

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; items: Branch[]; total: number };

interface Props {
  /** Bump this (e.g. after a create, edit, or delete) to force a refetch at the current page. */
  refreshToken?: number;
  /** Renders an Edit action per row when supplied. */
  onEdit?: (branch: Branch) => void;
  /** Renders a Delete action on active rows when supplied. */
  onDelete?: (branch: Branch) => void;
  /** Renders an Activate action on inactive rows when supplied. */
  onActivate?: (branch: Branch) => void;
}

export function BranchesList({ refreshToken, onEdit, onDelete, onActivate }: Props = {}) {
  const showActions = Boolean(onEdit || onDelete || onActivate);
  const [offset, setOffset] = useState(0);
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    getBranches({ limit: PAGE_SIZE, offset })
      .then((page) => {
        if (!cancelled) setState({ kind: "ready", items: page.items, total: page.total });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "Could not load branches.",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [offset, refreshToken]);

  if (state.kind === "loading") {
    return <p className="subtitle">Loading branches…</p>;
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
              <th>Code</th>
              <th>Name</th>
              <th>Location ID</th>
              <th>Active</th>
              {showActions ? <th></th> : null}
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={showActions ? 6 : 5} className="text-neutral-600">
                  No branches to show.
                </td>
              </tr>
            ) : (
              items.map((branch) => (
                <tr key={branch.id}>
                  <td className="font-mono text-xs">{branch.id}</td>
                  <td>{branch.code}</td>
                  <td>{branch.name}</td>
                  <td className="font-mono text-xs">{branch.location_id}</td>
                  <td>
                    <span className={"tag " + (branch.active ? "tag-accent" : "tag-neutral")}>
                      {branch.active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  {showActions ? (
                    <td className="text-right">
                      <div className="flex justify-end gap-ds-2">
                        {onEdit ? (
                          <button type="button" className="btn btn-secondary" onClick={() => onEdit(branch)}>
                            Edit
                          </button>
                        ) : null}
                        {branch.active
                          ? onDelete && (
                              <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={() => onDelete(branch)}
                              >
                                Delete
                              </button>
                            )
                          : onActivate && (
                              <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={() => onActivate(branch)}
                              >
                                Activate
                              </button>
                            )}
                      </div>
                    </td>
                  ) : null}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-neutral-600">
          {total === 0 ? "No branches" : `Showing ${from}–${to} of ${total}`}
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
