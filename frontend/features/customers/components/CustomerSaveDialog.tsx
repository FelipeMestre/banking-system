"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { validateDateOfBirth, validateIdentificationNumber, validatePersonName } from "../schemas/customer-fields";
import { CustomerForm } from "./CustomerForm";
import type { Customer } from "../types";

export interface CustomerDraft {
  identificationNumber: string;
  firstName: string;
  lastName: string;
  dateOfBirth: string;
  gender: string;
}

interface Props {
  title: string;
  /** Prefilled for edit, empty for create. */
  initialDraft?: CustomerDraft;
  onClose: () => void;
  onSaved: (customer: Customer) => void;
  /** The one thing that actually differs between create and edit — everything
   * else (validation, touched state, the Dialog chrome) is shared. */
  onSave: (draft: CustomerDraft) => Promise<Customer>;
}

const EMPTY_DRAFT: CustomerDraft = {
  identificationNumber: "",
  firstName: "",
  lastName: "",
  dateOfBirth: "",
  gender: "",
};

type Field = "identificationNumber" | "firstName" | "lastName" | "dateOfBirth";

/**
 * The validation + UX every customer popup shares, whether it's creating or
 * editing. AddCustomerDialog is a thin wrapper around this that only supplies
 * what's actually different: the title, the starting values, and which API
 * call `onSave` makes.
 */
export function CustomerSaveDialog({ title, initialDraft = EMPTY_DRAFT, onClose, onSaved, onSave }: Props) {
  const [draft, setDraft] = useState<CustomerDraft>(initialDraft);
  const [touched, setTouched] = useState<Record<Field, boolean>>({
    identificationNumber: false,
    firstName: false,
    lastName: false,
    dateOfBirth: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const errors = {
    identificationNumber: validateIdentificationNumber(draft.identificationNumber),
    firstName: validatePersonName(draft.firstName, "First name"),
    lastName: validatePersonName(draft.lastName, "Last name"),
    dateOfBirth: validateDateOfBirth(draft.dateOfBirth),
  };
  const isValid = Object.values(errors).every((error) => error === null);

  function markTouched(field: Field) {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }

  async function handleAccept() {
    setTouched({ identificationNumber: true, firstName: true, lastName: true, dateOfBirth: true });
    if (!isValid || submitting) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      const customer = await onSave({
        ...draft,
        identificationNumber: draft.identificationNumber.trim(),
        firstName: draft.firstName.trim(),
        lastName: draft.lastName.trim(),
      });
      onSaved(customer);
      onClose();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Could not save the customer.");
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      title={title}
      onClose={onClose}
      onAccept={handleAccept}
      acceptLabel={submitting ? "Saving…" : "Accept"}
      acceptDisabled={!isValid || submitting}
    >
      <CustomerForm
        identificationNumber={draft.identificationNumber}
        firstName={draft.firstName}
        lastName={draft.lastName}
        dateOfBirth={draft.dateOfBirth}
        gender={draft.gender}
        onIdentificationNumberChange={(value) => setDraft((prev) => ({ ...prev, identificationNumber: value }))}
        onFirstNameChange={(value) => setDraft((prev) => ({ ...prev, firstName: value }))}
        onLastNameChange={(value) => setDraft((prev) => ({ ...prev, lastName: value }))}
        onDateOfBirthChange={(value) => setDraft((prev) => ({ ...prev, dateOfBirth: value }))}
        onGenderChange={(value) => setDraft((prev) => ({ ...prev, gender: value }))}
        onFieldBlur={markTouched}
        errors={{
          identificationNumber: touched.identificationNumber ? errors.identificationNumber : null,
          firstName: touched.firstName ? errors.firstName : null,
          lastName: touched.lastName ? errors.lastName : null,
          dateOfBirth: touched.dateOfBirth ? errors.dateOfBirth : null,
        }}
      />
      {submitError ? <ErrorMessage message={submitError} /> : null}
    </Dialog>
  );
}
