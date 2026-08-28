"use client";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { deleteBranch } from "../api/delete-branch";
import type { Branch } from "../types";

interface Props {
  branch: Branch;
  onClose: () => void;
  onDeleted: (branch: Branch) => void;
}

export function DeleteBranchDialog({ branch, onClose, onDeleted }: Props) {
  return (
    <ConfirmDialog
      title="Delete branch"
      message={
        <p>
          Delete <strong>{branch.name}</strong>? This cannot be undone.
        </p>
      }
      confirmLabel="Delete"
      busyLabel="Deleting…"
      onClose={onClose}
      onConfirm={async () => {
        const deleted = await deleteBranch(branch.id);
        onDeleted(deleted);
      }}
    />
  );
}
