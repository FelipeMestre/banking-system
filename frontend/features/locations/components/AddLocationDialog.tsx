"use client";

import { createLocation } from "../api/create-location";
import { LocationSaveDialog } from "./LocationSaveDialog";
import type { Location } from "../types";

interface Props {
  onClose: () => void;
  onCreated: (location: Location) => void;
}

export function AddLocationDialog({ onClose, onCreated }: Props) {
  return (
    <LocationSaveDialog
      title="Add location"
      onClose={onClose}
      onSaved={onCreated}
      onSave={(name) => createLocation({ name })}
    />
  );
}
