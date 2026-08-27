"use client";

import { updateCustomer } from "../api/update-customer";
import { CustomerSaveDialog } from "./CustomerSaveDialog";
import type { Customer } from "../types";

interface Props {
  customer: Customer;
  onClose: () => void;
  onUpdated: (customer: Customer) => void;
}

export function EditCustomerDialog({ customer, onClose, onUpdated }: Props) {
  return (
    <CustomerSaveDialog
      title="Edit customer"
      initialDraft={{
        identificationNumber: customer.identification_number,
        firstName: customer.first_name,
        lastName: customer.last_name,
        dateOfBirth: customer.date_of_birth,
        gender: customer.gender ?? "",
      }}
      onClose={onClose}
      onSaved={onUpdated}
      onSave={(draft) =>
        updateCustomer(customer.id, {
          identification_number: draft.identificationNumber,
          first_name: draft.firstName,
          last_name: draft.lastName,
          date_of_birth: draft.dateOfBirth,
          gender: draft.gender.trim().length === 0 ? null : draft.gender,
        })
      }
    />
  );
}
