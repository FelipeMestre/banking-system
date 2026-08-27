"use client";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { deleteLocation } from "../api/delete-location";
import type { Location } from "../types";

interface Props {
  location: Location;
  onClose: () => void;
  onDeleted: (location: Location) => void;
}

export function DeleteLocationDialog({ location, onClose, onDeleted }: Props) {
  return (
    <ConfirmDialog
      title="Delete location"
      message={
        <p>
          Delete <strong>{location.name}</strong>? This cannot be undone.
        </p>
      }
      confirmLabel="Delete"
      busyLabel="Deleting…"
      onClose={onClose}
      onConfirm={async () => {
        const deleted = await deleteLocation(location.id);
        onDeleted(deleted);
      }}
    />
  );
}
