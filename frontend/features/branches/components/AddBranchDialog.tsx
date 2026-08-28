"use client";

import { createBranch } from "../api/create-branch";
import { BranchSaveDialog } from "./BranchSaveDialog";
import type { Branch } from "../types";

interface Props {
  onClose: () => void;
  onCreated: (branch: Branch) => void;
}

export function AddBranchDialog({ onClose, onCreated }: Props) {
  return (
    <BranchSaveDialog
      title="Add branch"
      onClose={onClose}
      onSaved={onCreated}
      onSave={(draft) => createBranch({ code: draft.code, name: draft.name, location_id: draft.locationId })}
    />
  );
}
