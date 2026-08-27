"use client";

import { createCustomer } from "../api/create-customer";
import { CustomerSaveDialog } from "./CustomerSaveDialog";
import type { Customer } from "../types";

interface Props {
  onClose: () => void;
  onCreated: (customer: Customer) => void;
}

export function AddCustomerDialog({ onClose, onCreated }: Props) {
  return (
    <CustomerSaveDialog
      title="Add customer"
      onClose={onClose}
      onSaved={onCreated}
      onSave={(draft) =>
        createCustomer({
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
