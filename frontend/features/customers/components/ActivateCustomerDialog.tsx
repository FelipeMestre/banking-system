"use client";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { activateCustomer } from "../api/activate-customer";
import type { Customer } from "../types";

interface Props {
  customer: Customer;
  onClose: () => void;
  onActivated: (customer: Customer) => void;
}

export function ActivateCustomerDialog({ customer, onClose, onActivated }: Props) {
  return (
    <ConfirmDialog
      title="Activate customer"
      message={
        <p>
          Activate <strong>{customer.first_name} {customer.last_name}</strong>?
        </p>
      }
      confirmLabel="Activate"
      busyLabel="Activating…"
      onClose={onClose}
      onConfirm={async () => {
        const activated = await activateCustomer(customer.id);
        onActivated(activated);
      }}
    />
  );
}
