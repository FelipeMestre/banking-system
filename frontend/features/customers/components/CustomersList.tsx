"use client";

import { useEffect, useState } from "react";
import { getCustomers } from "../api/get-customers";
import type { Customer } from "../types";

const PAGE_SIZE = 10;

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; items: Customer[]; total: number };

interface Props {
  /** Bump this (e.g. after a create, edit, or delete) to force a refetch at the current page. */
  refreshToken?: number;
  /** Renders an Edit action per row when supplied. */
  onEdit?: (customer: Customer) => void;
  /** Renders a Delete action on active rows when supplied. */
  onDelete?: (customer: Customer) => void;
  /** Renders an Activate action on inactive rows when supplied. */
  onActivate?: (customer: Customer) => void;
}

export function CustomersList({ refreshToken, onEdit, onDelete, onActivate }: Props = {}) {
  const showActions = Boolean(onEdit || onDelete || onActivate);
  const [offset, setOffset] = useState(0);
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    getCustomers({ limit: PAGE_SIZE, offset })
      .then((page) => {
        if (!cancelled) setState({ kind: "ready", items: page.items, total: page.total });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "Could not load customers.",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [offset, refreshToken]);

  if (state.kind === "loading") {
    return <p className="subtitle">Loading customers…</p>;
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
              <th>Identification Number</th>
              <th>First Name</th>
              <th>Last Name</th>
              <th>Date of Birth</th>
              <th>Gender</th>
              <th>Age</th>
              <th>Active</th>
              {showActions ? <th></th> : null}
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={showActions ? 9 : 8} className="text-neutral-600">
                  No customers to show.
                </td>
              </tr>
            ) : (
              items.map((customer) => (
                <tr key={customer.id}>
                  <td className="font-mono text-xs">{customer.id}</td>
                  <td>{customer.identification_number}</td>
                  <td>{customer.first_name}</td>
                  <td>{customer.last_name}</td>
                  <td>{customer.date_of_birth}</td>
                  <td>{customer.gender ?? "—"}</td>
                  <td>{customer.age}</td>
                  <td>
                    <span className={"tag " + (customer.active ? "tag-accent" : "tag-neutral")}>
                      {customer.active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  {showActions ? (
                    <td className="text-right">
                      <div className="flex justify-end gap-ds-2">
                        {onEdit ? (
                          <button type="button" className="btn btn-secondary" onClick={() => onEdit(customer)}>
                            Edit
                          </button>
                        ) : null}
                        {customer.active
                          ? onDelete && (
                              <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={() => onDelete(customer)}
                              >
                                Delete
                              </button>
                            )
                          : onActivate && (
                              <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={() => onActivate(customer)}
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
          {total === 0 ? "No customers" : `Showing ${from}–${to} of ${total}`}
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
