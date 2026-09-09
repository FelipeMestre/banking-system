"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ActivateBranchDialog } from "./ActivateBranchDialog";
import { AddBranchDialog } from "./AddBranchDialog";
import { BranchesList } from "./BranchesList";
import { DeleteBranchDialog } from "./DeleteBranchDialog";
import { EditBranchDialog } from "./EditBranchDialog";
import { usePermissions } from "@/lib/auth/usePermissions";
import type { Branch } from "../types";

/** What the Branches admin tab actually renders: the table plus the create/edit/delete/activate flows. */
export function BranchesPanel() {
  const { hasWriteAdmin } = usePermissions();
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<Branch | null>(null);
  const [deleting, setDeleting] = useState<Branch | null>(null);
  const [activating, setActivating] = useState<Branch | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  return (
    <div className="flex flex-col gap-ds-3">
      {hasWriteAdmin ? (
        <div className="flex justify-end">
          <Button type="button" onClick={() => setAddOpen(true)}>
            Add branch
          </Button>
        </div>
      ) : null}

      <BranchesList
        refreshToken={refreshToken}
        onEdit={hasWriteAdmin ? setEditing : undefined}
        onDelete={hasWriteAdmin ? setDeleting : undefined}
        onActivate={hasWriteAdmin ? setActivating : undefined}
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
