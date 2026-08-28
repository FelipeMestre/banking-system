"use client";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { deleteCustomer } from "../api/delete-customer";
import type { Customer } from "../types";

interface Props {
  customer: Customer;
  onClose: () => void;
  onDeleted: (customer: Customer) => void;
}

export function DeleteCustomerDialog({ customer, onClose, onDeleted }: Props) {
  return (
    <ConfirmDialog
      title="Delete customer"
      message={
        <p>
          Delete <strong>{customer.first_name} {customer.last_name}</strong>? This cannot be undone.
        </p>
      }
      confirmLabel="Delete"
      busyLabel="Deleting…"
      onClose={onClose}
      onConfirm={async () => {
        const deleted = await deleteCustomer(customer.id);
        onDeleted(deleted);
      }}
    />
  );
}
