"use client";

import { useState } from "react";
import { ActivateBranchDialog } from "./ActivateBranchDialog";
import { AddBranchDialog } from "./AddBranchDialog";
import { BranchesList } from "./BranchesList";
import { DeleteBranchDialog } from "./DeleteBranchDialog";
import { EditBranchDialog } from "./EditBranchDialog";
import type { Branch } from "../types";

/** What the Branches admin tab actually renders: the table plus the create/edit/delete/activate flows. */
export function BranchesPanel() {
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<Branch | null>(null);
  const [deleting, setDeleting] = useState<Branch | null>(null);
  const [activating, setActivating] = useState<Branch | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  return (
    <div className="flex flex-col gap-ds-3">
      <div className="flex justify-end">
        <button type="button" className="btn btn-primary" onClick={() => setAddOpen(true)}>
          Add branch
        </button>
      </div>

      <BranchesList
        refreshToken={refreshToken}
        onEdit={setEditing}
        onDelete={setDeleting}
        onActivate={setActivating}
      />

      {addOpen ? (
        <AddBranchDialog
          onClose={() => setAddOpen(false)}
          onCreated={() => setRefreshToken((token) => token + 1)}
        />
      ) : null}

      {editing ? (
        <EditBranchDialog
          branch={editing}
          onClose={() => setEditing(null)}
          onUpdated={() => setRefreshToken((token) => token + 1)}
        />
      ) : null}

      {deleting ? (
        <DeleteBranchDialog
          branch={deleting}
          onClose={() => setDeleting(null)}
          onDeleted={() => setRefreshToken((token) => token + 1)}
        />
      ) : null}

      {activating ? (
        <ActivateBranchDialog
          branch={activating}
          onClose={() => setActivating(null)}
          onActivated={() => setRefreshToken((token) => token + 1)}
        />
      ) : null}
    </div>
  );
}
