"use client";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { activateBranch } from "../api/activate-branch";
import type { Branch } from "../types";

interface Props {
  branch: Branch;
  onClose: () => void;
  onActivated: (branch: Branch) => void;
}

export function ActivateBranchDialog({ branch, onClose, onActivated }: Props) {
  return (
    <ConfirmDialog
      title="Activate branch"
      message={
        <p>
          Activate <strong>{branch.name}</strong>?
        </p>
      }
      confirmLabel="Activate"
      busyLabel="Activating…"
      onClose={onClose}
      onConfirm={async () => {
        const activated = await activateBranch(branch.id);
        onActivated(activated);
      }}
    />
  );
}
