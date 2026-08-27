"use client";

import { useState } from "react";
import { AddCustomerDialog } from "./AddCustomerDialog";
import { CustomersList } from "./CustomersList";
import { EditCustomerDialog } from "./EditCustomerDialog";
import type { Customer } from "../types";

/** What the Customers admin tab actually renders: the table plus the create/edit flows. */
export function CustomersPanel() {
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  return (
    <div className="flex flex-col gap-ds-3">
      <div className="flex justify-end">
        <button type="button" className="btn btn-primary" onClick={() => setAddOpen(true)}>
          Add customer
        </button>
      </div>

      <CustomersList refreshToken={refreshToken} onEdit={setEditing} />

      {addOpen ? (
        <AddCustomerDialog
          onClose={() => setAddOpen(false)}
          onCreated={() => setRefreshToken((token) => token + 1)}
        />
      ) : null}

      {editing ? (
        <EditCustomerDialog
          customer={editing}
          onClose={() => setEditing(null)}
          onUpdated={() => setRefreshToken((token) => token + 1)}
        />
      ) : null}
    </div>
  );
}
