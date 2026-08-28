"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { validateBranchCode, validateBranchLocationId, validateBranchName } from "../schemas/branch-fields";
import { BranchForm } from "./BranchForm";
import type { Branch } from "../types";

export interface BranchDraft {
  code: string;
  name: string;
  locationId: string;
}

interface Props {
  title: string;
  /** Prefilled for edit, empty for create. */
  initialDraft?: BranchDraft;
  onClose: () => void;
  onSaved: (branch: Branch) => void;
  /** The one thing that actually differs between create and edit — everything
   * else (validation, touched state, the Dialog chrome) is shared. */
  onSave: (draft: BranchDraft) => Promise<Branch>;
}

const EMPTY_DRAFT: BranchDraft = { code: "", name: "", locationId: "" };

type Field = "code" | "name" | "locationId";

/**
 * The validation + UX every branch popup shares, whether it's creating or
 * editing. AddBranchDialog and EditBranchDialog are thin wrappers around this
 * that only supply what's actually different: the title, the starting
 * values, and which API call `onSave` makes.
 */
export function BranchSaveDialog({ title, initialDraft = EMPTY_DRAFT, onClose, onSaved, onSave }: Props) {
  const [draft, setDraft] = useState<BranchDraft>(initialDraft);
  const [touched, setTouched] = useState<Record<Field, boolean>>({
    code: false,
    name: false,
    locationId: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const errors = {
    code: validateBranchCode(draft.code),
    name: validateBranchName(draft.name),
    locationId: validateBranchLocationId(draft.locationId),
  };
  const isValid = Object.values(errors).every((error) => error === null);

  function markTouched(field: Field) {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }

  async function handleAccept() {
    setTouched({ code: true, name: true, locationId: true });
    if (!isValid || submitting) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      const branch = await onSave({ ...draft, code: draft.code.trim(), name: draft.name.trim() });
      onSaved(branch);
      onClose();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Could not save the branch.");
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
      <BranchForm
        code={draft.code}
        name={draft.name}
        locationId={draft.locationId}
        onCodeChange={(value) => setDraft((prev) => ({ ...prev, code: value }))}
        onNameChange={(value) => setDraft((prev) => ({ ...prev, name: value }))}
        onLocationIdChange={(value) => setDraft((prev) => ({ ...prev, locationId: value }))}
        onFieldBlur={markTouched}
        errors={{
          code: touched.code ? errors.code : null,
          name: touched.name ? errors.name : null,
          locationId: touched.locationId ? errors.locationId : null,
        }}
      />
      {submitError ? <ErrorMessage message={submitError} /> : null}
    </Dialog>
  );
}
