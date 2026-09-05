"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ActivateCustomerDialog } from "./ActivateCustomerDialog";
import { AddCustomerDialog } from "./AddCustomerDialog";
import { CustomersList } from "./CustomersList";
import { DeleteCustomerDialog } from "./DeleteCustomerDialog";
import { EditCustomerDialog } from "./EditCustomerDialog";
import { usePermissions } from "@/lib/auth/usePermissions";
import type { Customer } from "../types";

/** What the Customers admin tab actually renders: the table plus the create/edit/delete/activate flows. */
export function CustomersPanel() {
  const { hasWriteAdmin } = usePermissions();
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [deleting, setDeleting] = useState<Customer | null>(null);
  const [activating, setActivating] = useState<Customer | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  return (
    <div className="flex flex-col gap-ds-3">
      {hasWriteAdmin ? (
        <div className="flex justify-end">
          <Button type="button" onClick={() => setAddOpen(true)}>
            Add customer
          </Button>
        </div>
      ) : null}

      <CustomersList
        refreshToken={refreshToken}
        onEdit={hasWriteAdmin ? setEditing : undefined}
        onDelete={hasWriteAdmin ? setDeleting : undefined}
        onActivate={hasWriteAdmin ? setActivating : undefined}
      />

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

      {deleting ? (
        <DeleteCustomerDialog
          customer={deleting}
          onClose={() => setDeleting(null)}
          onDeleted={() => setRefreshToken((token) => token + 1)}
        />
      ) : null}

      {activating ? (
        <ActivateCustomerDialog
          customer={activating}
          onClose={() => setActivating(null)}
          onActivated={() => setRefreshToken((token) => token + 1)}
        />
      ) : null}
    </div>
  );
}
