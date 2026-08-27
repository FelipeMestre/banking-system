"use client";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { activateLocation } from "../api/activate-location";
import type { Location } from "../types";

interface Props {
  location: Location;
  onClose: () => void;
  onActivated: (location: Location) => void;
}

export function ActivateLocationDialog({ location, onClose, onActivated }: Props) {
  return (
    <ConfirmDialog
      title="Activate location"
      message={
        <p>
          Activate <strong>{location.name}</strong>?
        </p>
      }
      confirmLabel="Activate"
      busyLabel="Activating…"
      onClose={onClose}
      onConfirm={async () => {
        const activated = await activateLocation(location.id);
        onActivated(activated);
      }}
    />
  );
}
