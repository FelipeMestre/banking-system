"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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
    return <p className="m-0 text-[0.9rem] text-neutral-600">Loading customers…</p>;
  }

  if (state.kind === "error") {
    return <p className="m-0 text-[0.9rem] text-neutral-600">{state.message}</p>;
  }

  const { items, total } = state;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);
  const canPrev = offset > 0;
  const canNext = to < total;

  return (
    <div className="flex flex-col gap-ds-3">
      <div className="overflow-x-auto border-2 border-divider">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Identification Number</TableHead>
              <TableHead>First Name</TableHead>
              <TableHead>Last Name</TableHead>
              <TableHead>Date of Birth</TableHead>
              <TableHead>Gender</TableHead>
              <TableHead>Age</TableHead>
              <TableHead>Active</TableHead>
              {showActions ? <TableHead></TableHead> : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={showActions ? 9 : 8} className="text-neutral-600">
                  No customers to show.
                </TableCell>
              </TableRow>
            ) : (
              items.map((customer) => (
                <TableRow key={customer.id}>
                  <TableCell className="font-mono text-xs whitespace-normal break-all">{customer.id}</TableCell>
                  <TableCell>{customer.identification_number}</TableCell>
                  <TableCell>{customer.first_name}</TableCell>
                  <TableCell>{customer.last_name}</TableCell>
                  <TableCell>{customer.date_of_birth}</TableCell>
                  <TableCell>{customer.gender ?? "—"}</TableCell>
                  <TableCell>{customer.age}</TableCell>
                  <TableCell>
                    <Badge variant={customer.active ? "default" : "secondary"}>
                      {customer.active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  {showActions ? (
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-ds-2">
                        {onEdit ? (
                          <Button type="button" variant="outline" onClick={() => onEdit(customer)}>
                            Edit
                          </Button>
                        ) : null}
                        {customer.active
                          ? onDelete && (
                              <Button type="button" variant="outline" onClick={() => onDelete(customer)}>
                                Delete
                              </Button>
                            )
                          : onActivate && (
                              <Button type="button" variant="outline" onClick={() => onActivate(customer)}>
                                Activate
                              </Button>
                            )}
                      </div>
                    </TableCell>
                  ) : null}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-neutral-600">
          {total === 0 ? "No customers" : `Showing ${from}–${to} of ${total}`}
        </span>
        <div className="flex gap-ds-2">
          <Button
            type="button"
            variant="outline"
            disabled={!canPrev}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={!canNext}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
