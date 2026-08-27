"use client";

import { useState } from "react";
import { ActivateLocationDialog } from "./ActivateLocationDialog";
import { AddLocationDialog } from "./AddLocationDialog";
import { DeleteLocationDialog } from "./DeleteLocationDialog";
import { EditLocationDialog } from "./EditLocationDialog";
import { LocationsList } from "./LocationsList";
import type { Location } from "../types";

/** What the Locations admin tab actually renders: the table plus the create/edit/delete/activate flows. */
export function LocationsPanel() {
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<Location | null>(null);
  const [deleting, setDeleting] = useState<Location | null>(null);
  const [activating, setActivating] = useState<Location | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  return (
    <div className="flex flex-col gap-ds-3">
      <div className="flex justify-end">
        <button type="button" className="btn btn-primary" onClick={() => setAddOpen(true)}>
          Add location
        </button>
      </div>

      <LocationsList
        refreshToken={refreshToken}
        onEdit={setEditing}
        onDelete={setDeleting}
        onActivate={setActivating}
      />

      {addOpen ? (
        <AddLocationDialog
          onClose={() => setAddOpen(false)}
          onCreated={() => setRefreshToken((token) => token + 1)}
        />
      ) : null}

      {editing ? (
        <EditLocationDialog
          location={editing}
          onClose={() => setEditing(null)}
          onUpdated={() => setRefreshToken((token) => token + 1)}
        />
      ) : null}

      {deleting ? (
        <DeleteLocationDialog
          location={deleting}
          onClose={() => setDeleting(null)}
          onDeleted={() => setRefreshToken((token) => token + 1)}
        />
      ) : null}

      {activating ? (
        <ActivateLocationDialog
          location={activating}
          onClose={() => setActivating(null)}
          onActivated={() => setRefreshToken((token) => token + 1)}
        />
      ) : null}
    </div>
  );
}
