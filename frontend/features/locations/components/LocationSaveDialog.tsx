"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { validateLocationName } from "../schemas/location-name";
import { LocationForm } from "./LocationForm";
import type { Location } from "../types";

interface Props {
  title: string;
  /** Prefilled for edit, empty for create. */
  initialName?: string;
  onClose: () => void;
  onSaved: (location: Location) => void;
  /** The one thing that actually differs between create and edit — everything
   * else (validation, touched state, the Dialog chrome) is shared. */
  onSave: (name: string) => Promise<Location>;
}

/**
 * The validation + UX every location popup shares, whether it's creating or
 * editing. AddLocationDialog and EditLocationDialog are thin wrappers around
 * this that only supply what's actually different: the title, the starting
 * value, and which API call `onSave` makes.
 */
export function LocationSaveDialog({ title, initialName = "", onClose, onSaved, onSave }: Props) {
  const [name, setName] = useState(initialName);
  const [touched, setTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const validationError = validateLocationName(name);
  const isValid = validationError === null;

  async function handleAccept() {
    setTouched(true);
    if (!isValid || submitting) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      const location = await onSave(name.trim());
      onSaved(location);
      onClose();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Could not save the location.");
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
      <LocationForm
        name={name}
        onNameChange={setName}
        onNameBlur={() => setTouched(true)}
        error={touched ? validationError : null}
      />
      {submitError ? <p className="hint">{submitError}</p> : null}
    </Dialog>
  );
}
