"use client";

import { updateLocation } from "../api/update-location";
import { LocationSaveDialog } from "./LocationSaveDialog";
import type { Location } from "../types";

interface Props {
  location: Location;
  onClose: () => void;
  onUpdated: (location: Location) => void;
}

export function EditLocationDialog({ location, onClose, onUpdated }: Props) {
  return (
    <LocationSaveDialog
      title="Edit location"
      initialName={location.name}
      onClose={onClose}
      onSaved={onUpdated}
      onSave={(name) => updateLocation(location.id, { name })}
    />
  );
}
